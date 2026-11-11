from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from mesa_platform.http import ApiError
from mesa_platform.http_client import JsonResponse
from services.deliveries.internal import AddressInput, DispatchInput, LookupInput
from services.orders.dependencies import dependency_error
from services.orders.lifecycle import NEXT_STATE, previous_action
from services.orders.orchestration import validate_delivery, without_address
from services.orders.schemas import Checkout, OrderView
from services.orders.transition_routes import resume_dispatch

PRODUCT_ID = "24a548d7-0135-4125-a4e4-dfb69c2c4064"
CHECKOUT = {
    "configuration_revision": 1,
    "catalog_revision": 1,
    "origin": "client",
    "fulfillment": "delivery",
    "customer_name": "Cliente",
    "address": "Rua Demonstrativa, 10",
    "items": [{"product_id": PRODUCT_ID, "quantity": 1, "expected_unit_price_cents": 3290}],
}


@pytest.mark.parametrize("origin", ["client", "counter"])
def test_delivery_checkout_trims_and_keeps_address(origin):
    checkout = Checkout.model_validate({**CHECKOUT, "origin": origin, "address": "  Rua A, 1  "})

    assert checkout.address == "Rua A, 1"


@pytest.mark.parametrize("address", [None, "", "   ", "x" * 501, 10])
def test_delivery_checkout_requires_valid_address(address):
    with pytest.raises(ValidationError):
        Checkout.model_validate({**CHECKOUT, "address": address})


def test_delivery_checkout_accepts_address_limit():
    assert len(Checkout.model_validate({**CHECKOUT, "address": "x" * 500}).address) == 500


def test_pickup_checkout_rejects_address_and_omits_it_from_payload():
    with pytest.raises(ValidationError, match="Endereço só é aceito"):
        Checkout.model_validate({**CHECKOUT, "fulfillment": "pickup"})

    pickup = {key: value for key, value in CHECKOUT.items() if key != "address"}
    payload = Checkout.model_validate({**pickup, "fulfillment": "pickup"}).model_dump(mode="json", exclude_none=True)
    assert "address" not in payload


@pytest.mark.parametrize("field,value", [("fee_cents", 0), ("subtotal_cents", 1), ("total_cents", 1)])
def test_checkout_never_accepts_client_amounts(field, value):
    with pytest.raises(ValidationError):
        Checkout.model_validate({**CHECKOUT, field: value})


def test_address_is_removed_from_operation_payload():
    assert without_address(CHECKOUT) == {key: value for key, value in CHECKOUT.items() if key != "address"}
    assert "address" in CHECKOUT


def test_delivery_receipt_must_match_operation_and_fixed_fee():
    operation = SimpleNamespace(id=uuid4(), order_id=uuid4())
    receipt = {"order_id": str(operation.order_id), "operation_id": str(operation.id), "fee_cents": 500}

    assert validate_delivery(operation, receipt) == {"fee_cents": 500}

    for change in [{"fee_cents": 600}, {"order_id": str(uuid4())}, {"operation_id": str(uuid4())}, {"fee_cents": None}]:
        with pytest.raises(ApiError) as caught:
            validate_delivery(operation, {**receipt, **change})
        assert caught.value.status == 503


def test_delivery_conflicts_are_retried_not_rejected():
    response = JsonResponse(409, {"error": {"code": "idempotency_conflict", "message": "Conflito"}})

    assert dependency_error("deliveries", response).code == "dependency_unavailable"
    assert dependency_error("catalog", response).code == "idempotency_conflict"


def test_only_delivery_orders_are_dispatched():
    assert NEXT_STATE["delivery"]["ready"] == "dispatched"
    assert NEXT_STATE["delivery"]["dispatched"] == "completed"
    assert NEXT_STATE["pickup"]["ready"] == "completed"
    assert "dispatched" not in NEXT_STATE["pickup"].values()


@pytest.mark.parametrize("address", ["", "   ", "x" * 501, None])
def test_deliveries_rejects_invalid_address(address):
    with pytest.raises(ValidationError):
        AddressInput.model_validate({"operation_id": str(uuid4()), "address": address})


def test_deliveries_requires_aware_dispatch_time():
    transition_id = uuid4()
    accepted = DispatchInput.model_validate({"transition_id": str(transition_id), "dispatched_at": "2026-11-11T12:00:00+00:00"})

    assert accepted.transition_id == transition_id
    with pytest.raises(ValidationError):
        DispatchInput.model_validate({"transition_id": str(transition_id), "dispatched_at": "2026-11-11T12:00:00"})


@pytest.mark.parametrize("count", [0, 101])
def test_deliveries_lookup_limits(count):
    with pytest.raises(ValidationError):
        LookupInput.model_validate({"order_ids": [str(UUID(int=index + 1)) for index in range(count)]})


class FinishedDuringReplay:
    """No transition on the first lookup; the worker has finished the dispatch by the second."""

    def __init__(self, dispatch, transition):
        self.lookups = iter([None, dispatch])
        self.transition = transition

    def scalar(self, query):
        return next(self.lookups)

    def get(self, model, identifier):
        assert identifier == self.transition.id
        return self.transition


def test_replay_returns_dispatch_finished_between_lookups():
    order = OrderView(
        id=uuid4(), number=7, origin="client", fulfillment="delivery", customer_name="Cliente",
        state="dispatched", version=4, configuration_revision=1, catalog_revision=1,
        items=[], fee_cents=500, total_cents=3790,
        created_at="2026-11-11T12:00:00+00:00", updated_at="2026-11-11T12:05:00+00:00",
    )
    dispatch = SimpleNamespace(id=uuid4(), payload_hash="same", state="succeeded")
    transition = SimpleNamespace(id=dispatch.id, result=order.model_dump(mode="json"))

    replay = previous_action(FinishedDuringReplay(dispatch, transition), "operator:op", uuid4(), "same")

    assert isinstance(replay, OrderView)
    assert replay.state == "dispatched"


class WorkerFinishesAfterCommit:
    """The worker completes the resumed dispatch as soon as the resume is committed."""

    def __init__(self, operation):
        self.operation = operation

    def scalar(self, query):
        return self.operation

    def add(self, row):
        pass

    def commit(self):
        self.operation.state = "succeeded"


def test_resume_confirmation_survives_worker_finishing_after_commit(monkeypatch):
    monkeypatch.setattr("services.orders.transition_routes.authorize_staff", lambda *args, **kwargs: {"username": "admin"})
    operation = SimpleNamespace(
        id=uuid4(), order_id=uuid4(), state="needs_attention", attempts=10,
        error={"code": "dependency_unavailable"}, error_status=503,
    )
    response = SimpleNamespace(status_code=200)

    accepted = resume_dispatch(operation.id, request=None, response=response, db=WorkerFinishesAfterCommit(operation))

    assert accepted.state == "pending"
    assert response.status_code == 202
    assert operation.state == "succeeded"
