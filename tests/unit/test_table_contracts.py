from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mesa_platform.http import ApiError
from mesa_platform.http_client import JsonResponse
from services.configuration.internal import AdmissionInput, required_features
from services.orders.dependencies import dependency_error
from services.orders.errors import is_business_rejection
from services.orders.lifecycle import NEXT_STATE
from services.orders.orchestration import validate_table_receipt
from services.orders.schemas import Checkout
from services.orders.table_access import tablet_creator, verify_table_context
from services.tables.schemas import AvailabilityUpdate

PRODUCT_ID = "24a548d7-0135-4125-a4e4-dfb69c2c4064"
TABLE_ID = str(uuid4())
BASE = {
    "configuration_revision": 1,
    "catalog_revision": 1,
    "fulfillment": "table",
    "items": [{"product_id": PRODUCT_ID, "quantity": 1, "expected_unit_price_cents": 3290}],
}


@pytest.mark.parametrize("origin", ["client", "counter"])
def test_client_and_counter_need_name_and_table(origin):
    checkout = Checkout.model_validate({**BASE, "origin": origin, "customer_name": "Ana", "table_id": TABLE_ID})

    assert str(checkout.table_id) == TABLE_ID
    with pytest.raises(ValidationError, match="Escolha a mesa"):
        Checkout.model_validate({**BASE, "origin": origin, "customer_name": "Ana"})
    with pytest.raises(ValidationError, match="Informe seu nome"):
        Checkout.model_validate({**BASE, "origin": origin, "table_id": TABLE_ID})


def test_tablet_identifies_only_by_credential():
    checkout = Checkout.model_validate({**BASE, "origin": "tablet"})

    assert checkout.customer_name is None and checkout.table_id is None
    for extra in [{"customer_name": "Ana"}, {"table_id": TABLE_ID}]:
        with pytest.raises(ValidationError, match="credencial"):
            Checkout.model_validate({**BASE, "origin": "tablet", **extra})


@pytest.mark.parametrize("fulfillment", ["pickup", "delivery"])
def test_tablet_only_orders_for_tables(fulfillment):
    with pytest.raises(ValidationError, match="só cria pedidos para mesa"):
        Checkout.model_validate({**BASE, "origin": "tablet", "fulfillment": fulfillment, "address": "Rua A"})


def test_table_id_belongs_only_to_table_orders():
    with pytest.raises(ValidationError, match="Mesa só é aceita"):
        Checkout.model_validate({
            **BASE, "origin": "client", "fulfillment": "pickup", "customer_name": "Ana", "table_id": TABLE_ID,
        })


def test_admission_requires_table_and_tablet_features():
    admission = {"principal": "tablet:x", "revision": 1, "origin": "tablet", "fulfillment": "table"}
    tablet = AdmissionInput.model_validate(admission)
    client = AdmissionInput.model_validate({**admission, "principal": "customer:x", "origin": "client"})

    assert [feature for feature, _ in required_features(tablet)] == ["tables", "tablet"]
    assert [feature for feature, _ in required_features(client)] == ["tables"]
    with pytest.raises(ValidationError):
        AdmissionInput.model_validate({**admission, "fulfillment": "pickup"})


@pytest.mark.parametrize("status,code,rejected", [
    (404, "table_not_found", True),
    (409, "table_unavailable", True),
    (409, "idempotency_conflict", True),
    (403, "forbidden", False),
    (500, "internal_error", False),
    (409, "unexpected", False),
])
def test_table_failures_are_rejections_only_when_known(status, code, rejected):
    error = dependency_error("tables", JsonResponse(status, {"error": {"code": code, "message": "Falha"}}))

    assert is_business_rejection(error) is rejected
    if not rejected:
        assert error.status == 503


def test_table_receipt_must_match_operation():
    operation = SimpleNamespace(id=uuid4(), payload={"table_id": TABLE_ID})
    receipt = {"operation_id": str(operation.id), "table_id": TABLE_ID, "table_number": 5}

    assert validate_table_receipt(operation, receipt) == {"table_number": 5}
    for change in [{"operation_id": str(uuid4())}, {"table_id": str(uuid4())}, {"table_number": 0}]:
        with pytest.raises(ApiError) as caught:
            validate_table_receipt(operation, {**receipt, **change})
        assert caught.value.status == 503


def test_table_orders_skip_dispatch():
    assert NEXT_STATE["table"] == NEXT_STATE["pickup"]


def test_availability_update_is_strict():
    with pytest.raises(ValidationError):
        AvailabilityUpdate.model_validate({"expected_version": 1, "available": "false"})


def tablet_request(headers=None):
    return SimpleNamespace(
        cookies={"mesa_table": "opaque-token"}, headers=headers or {}, state=SimpleNamespace(request_id="id"),
    )


@pytest.mark.parametrize("status,body,expected", [
    (401, {"error": {"code": "invalid_table_context"}}, (401, "invalid_table_context")),
    (403, {"error": {"code": "invalid_csrf"}}, (403, "invalid_csrf")),
    (403, {"error": {"code": "forbidden"}}, (503, "tables_unavailable")),
    (500, None, (503, "tables_unavailable")),
    (200, {"context_id": "invalid"}, (503, "tables_unavailable")),
])
def test_credential_errors_differ_from_integration_failures(monkeypatch, status, body, expected):
    monkeypatch.setenv("MESA_ORDERS_ACCESS_KEY", "test-key")
    monkeypatch.setattr("services.orders.table_access.post_json", lambda *args, **kwargs: JsonResponse(status, body))

    with pytest.raises(ApiError) as caught:
        verify_table_context(tablet_request())
    assert (caught.value.status, caught.value.code) == expected


def test_retry_from_another_context_is_refused(monkeypatch):
    context = {"context_id": str(uuid4()), "table_id": TABLE_ID, "table_number": 3}
    monkeypatch.setenv("MESA_ORDERS_ACCESS_KEY", "test-key")
    monkeypatch.setattr("services.orders.table_access.post_json", lambda *args, **kwargs: JsonResponse(200, context))

    accepted = tablet_creator(tablet_request({"X-CSRF-Token": "csrf", "X-Table-Context": context["context_id"]}))
    assert str(accepted.context_id) == context["context_id"]

    with pytest.raises(ApiError) as caught:
        tablet_creator(tablet_request({"X-CSRF-Token": "csrf", "X-Table-Context": str(uuid4())}))
    assert caught.value.code == "table_context_changed"
