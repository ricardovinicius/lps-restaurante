"""Delivery checkout and dispatch across Pedidos, Entregas, Configuração and Catálogo."""

from concurrent.futures import ThreadPoolExecutor
import json
import time
from uuid import uuid4

import httpx
import pytest

from tests.integration.support import (
    CONFIG, ORDERS, confirmed, create, database_script, payload_for, transition,
)

ADDRESS = "Rua das Entregas, 50 - Centro"
REQUEST_ID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture
def delivery_shop(shop):
    admin, operator, customer, compose, product = shop
    current = admin.get(CONFIG).json()
    response = admin.put(CONFIG, json={
        "expected_revision": current["revision"],
        "features": {**current["features"], "pickup": True, "delivery": True},
    })
    assert response.status_code == 200, response.text
    yield admin, operator, customer, compose, product


def delivery_payload(admin, product, **changes):
    return payload_for(admin, product, fulfillment="delivery", address=ADDRESS, **changes)


def wait_for(read, accept, timeout=25):
    deadline = time.monotonic() + timeout
    value = read()
    while not accept(value) and time.monotonic() < deadline:
        time.sleep(0.3)
        value = read()

    assert accept(value), value
    return value


def advance(operator, order, *states):
    for state in states:
        response = transition(operator, order, state)
        assert response.status_code == 200, response.text
        order = response.json()

    return order


def stored_delivery(compose, order_id):
    output = database_script(compose, "deliveries", """
rows = connection.execute(text(
    "SELECT address, fee_cents, transition_id FROM deliveries WHERE order_id=:order_id"
), parameters).all()
print(json.dumps([[row.address, row.fee_cents, str(row.transition_id) if row.transition_id else None] for row in rows]))
""", order_id=order_id)
    return json.loads(output.splitlines()[-1])


def addresses_kept_by_orders(compose):
    output = database_script(compose, "orders", """
print(connection.scalar(text(
    "SELECT count(*) FROM checkout_operations "
    "WHERE payload::jsonb ? 'address' AND state IN ('succeeded', 'rejected')"
)))
""")
    return int(output.splitlines()[-1])


def postpone_retries(compose, table, column, value):
    """Hold the worker back only once no attempt owns the lease, so the test is deterministic."""
    def update():
        output = database_script(compose, "orders", f"""
result = connection.execute(text(
    "UPDATE {table} SET next_attempt_at=now() + interval '1 hour' "
    "WHERE {column}=:value AND lease_id IS NULL"
), parameters)
print(result.rowcount)
""", value=value)
        return output.splitlines()[-1]

    wait_for(update, lambda count: count == "1")


def test_delivery_lifecycle_fee_address_ownership_and_dispatch_replay(delivery_shop, deployment):
    admin, operator, customer, compose, product = delivery_shop
    payload = delivery_payload(admin, product)
    key = str(uuid4())
    order = confirmed(customer, create(customer, payload, key))

    assert order["fulfillment"] == "delivery"
    assert order["fee_cents"] == 500
    assert order["total_cents"] == product["price_cents"] * 2 + 500
    assert order["delivery"] == {"available": True, "address": ADDRESS, "dispatched_at": None}
    assert confirmed(customer, create(customer, payload, key))["id"] == order["id"]
    assert create(customer, {**payload, "address": "Outro endereço"}, key).status_code == 409
    assert stored_delivery(compose, order["id"]) == [[ADDRESS, 500, None]]
    assert addresses_kept_by_orders(compose) == 0

    queued = operator.get(ORDERS + "/queue", params={"fulfillment": "delivery"}).json()["items"]
    assert [item["delivery"]["address"] for item in queued if item["id"] == order["id"]] == [ADDRESS]
    with httpx.Client(base_url=deployment[0]) as other:
        other.post(ORDERS + "/customer-contexts")
        assert other.get(ORDERS + "/orders/" + order["id"]).status_code == 404
        assert other.get("/internal/v1/deliveries/lookup").status_code == 404
        assert other.get("/api/deliveries/v1/deliveries/" + order["id"]).status_code == 404

    ready = advance(operator, order, "preparing", "ready")
    assert transition(operator, ready, "completed").status_code == 409

    dispatch_key = str(uuid4())
    dispatched = transition(operator, ready, "dispatched", dispatch_key)
    assert dispatched.status_code == 200, dispatched.text
    assert dispatched.json()["state"] == "dispatched"
    assert dispatched.json()["delivery"]["dispatched_at"] is not None
    replay = transition(operator, ready, "dispatched", dispatch_key)
    assert replay.status_code == 200
    assert replay.json()["version"] == dispatched.json()["version"]
    assert transition(operator, ready, "dispatched").status_code == 409

    completed = advance(operator, dispatched.json(), "completed")
    assert completed["state"] == "completed"
    assert customer.get(ORDERS + "/orders/" + order["id"]).json()["delivery"]["address"] == ADDRESS
    assert stored_delivery(compose, order["id"])[0][2] is not None


def test_counter_creates_delivery_and_invalid_addresses_leave_no_data(delivery_shop):
    admin, operator, customer, compose, product = delivery_shop
    counter = confirmed(operator, create(operator, delivery_payload(admin, product, origin="counter")))
    assert counter["origin"] == "counter"
    assert counter["delivery"]["address"] == ADDRESS
    assert customer.get(ORDERS + "/orders/" + counter["id"]).status_code == 404

    count_before = database_script(compose, "deliveries", """
print(connection.scalar(text("SELECT count(*) FROM deliveries")))
""").splitlines()[-1]
    payload = delivery_payload(admin, product)
    for change in [{"address": None}, {"address": "   "}, {"address": "x" * 501}]:
        response = create(customer, {**payload, **change})
        assert response.status_code == 422, response.text

    pickup_with_address = {**payload_for(admin, product), "address": ADDRESS}
    assert create(customer, pickup_with_address).status_code == 422
    assert customer.get(ORDERS + "/my-orders").json()["items"] == []
    assert database_script(compose, "deliveries", """
print(connection.scalar(text("SELECT count(*) FROM deliveries")))
""").splitlines()[-1] == count_before


def test_disabling_delivery_blocks_new_orders_and_preserves_existing(delivery_shop):
    admin, operator, customer, _, product = delivery_shop
    order = confirmed(customer, create(customer, delivery_payload(admin, product)))

    current = admin.get(CONFIG).json()
    response = admin.put(CONFIG, json={
        "expected_revision": current["revision"],
        "features": {**current["features"], "pickup": True, "delivery": False},
    })
    assert response.status_code == 200, response.text

    blocked = create(customer, delivery_payload(admin, product))
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["error"]["code"] == "feature_disabled"

    completed = advance(operator, order, "preparing", "ready", "dispatched", "completed")
    assert completed["state"] == "completed"
    assert customer.get(ORDERS + "/orders/" + order["id"]).json()["state"] == "completed"


def test_checkout_recovers_after_remote_commit_lost_response_and_restart(delivery_shop):
    admin, operator, customer, compose, product = delivery_shop
    payload = delivery_payload(admin, product)
    key = str(uuid4())

    compose("stop", "deliveries")
    try:
        pending = create(customer, payload, key)
        assert pending.status_code == 202, pending.text
        operation_id = pending.json()["operation_id"]
        status = customer.get(ORDERS + "/operations/" + operation_id).json()
        assert status["state"] == "pending"
        assert status["error"]["code"] == "dependency_unavailable"
        postpone_retries(compose, "checkout_operations", "id", operation_id)
    finally:
        compose("up", "-d", "--no-deps", "--wait", "deliveries")

    # Entregas commits the address, but Pedidos never sees the response.
    database_script(compose, "orders", """
from services.orders.dependencies import register_delivery
row = connection.execute(text(
    "SELECT id, order_id, payload FROM checkout_operations WHERE id=:operation_id"
), parameters).one()
register_delivery(row, parameters["request_id"])
""", operation_id=operation_id, request_id=REQUEST_ID)

    compose("up", "-d", "--force-recreate", "--no-deps", "--wait", "orders")
    database_script(compose, "orders", """
connection.execute(text("UPDATE checkout_operations SET next_attempt_at=now() WHERE id=:operation_id"), parameters)
""", operation_id=operation_id)

    status = wait_for(
        lambda: customer.get(ORDERS + "/operations/" + operation_id).json(),
        lambda value: value["state"] == "succeeded",
    )
    order = status["order"]
    assert order["fee_cents"] == 500
    assert order["delivery"]["address"] == ADDRESS
    assert stored_delivery(compose, order["id"]) == [[ADDRESS, 500, None]]
    assert confirmed(customer, create(customer, payload, key))["id"] == order["id"]
    assert len(customer.get(ORDERS + "/my-orders").json()["items"]) == 1
    assert addresses_kept_by_orders(compose) == 0


def test_dispatch_timeout_degrades_reads_and_recovers_after_restart(delivery_shop):
    admin, operator, customer, compose, product = delivery_shop
    order = confirmed(customer, create(customer, delivery_payload(admin, product)))
    pickup = confirmed(customer, create(customer, payload_for(admin, product)))
    ready = advance(operator, order, "preparing", "ready")
    dispatch_key = str(uuid4())

    compose("pause", "deliveries")
    try:
        pending = transition(operator, ready, "dispatched", dispatch_key)
        assert pending.status_code == 202, pending.text
        assert pending.json()["state"] == "pending"
        assert transition(operator, ready, "completed").status_code == 409
        assert transition(operator, ready, "dispatched").status_code == 409

        active = customer.get(ORDERS + "/my-orders", params={"status": "active"})
        assert active.status_code == 200, active.text
        by_id = {item["id"]: item for item in active.json()["items"]}
        assert by_id[order["id"]]["state"] == "ready"
        assert by_id[order["id"]]["dispatch_state"] == "pending"
        assert by_id[order["id"]]["delivery"] == {"available": False, "address": None, "dispatched_at": None}
        assert by_id[pickup["id"]]["delivery"] is None
        postpone_retries(compose, "dispatch_operations", "order_id", order["id"])
    finally:
        compose("unpause", "deliveries")

    # Entregas records the dispatch, but the confirmation never reaches Pedidos.
    database_script(compose, "orders", """
from services.orders.dependencies import dispatch_delivery
row = connection.execute(text(
    "SELECT id, order_id, dispatched_at FROM dispatch_operations WHERE order_id=:order_id"
), parameters).one()
dispatch_delivery(row, parameters["request_id"])
""", order_id=order["id"], request_id=REQUEST_ID)
    assert customer.get(ORDERS + "/orders/" + order["id"]).json()["state"] == "ready"

    compose("up", "-d", "--force-recreate", "--no-deps", "--wait", "orders")
    database_script(compose, "orders", """
connection.execute(text("UPDATE dispatch_operations SET next_attempt_at=now() WHERE order_id=:order_id"), parameters)
""", order_id=order["id"])

    dispatched = wait_for(
        lambda: customer.get(ORDERS + "/orders/" + order["id"]).json(),
        lambda value: value["state"] == "dispatched",
    )
    assert dispatched["dispatch_state"] is None
    assert dispatched["delivery"]["dispatched_at"] is not None
    replay = transition(operator, ready, "dispatched", dispatch_key)
    assert replay.status_code == 200, replay.text
    assert replay.json()["version"] == dispatched["version"]

    transitions = database_script(compose, "orders", """
print(connection.scalar(text(
    "SELECT count(*) FROM transitions WHERE order_id=:order_id AND target_state='dispatched'"
), parameters))
""", order_id=order["id"])
    assert transitions.splitlines()[-1] == "1"
    assert advance(operator, dispatched, "completed")["state"] == "completed"


def test_exhausted_dispatch_requires_authorized_audited_resume(delivery_shop):
    admin, operator, customer, compose, product = delivery_shop
    order = confirmed(customer, create(customer, delivery_payload(admin, product)))
    ready = advance(operator, order, "preparing", "ready")

    compose("stop", "deliveries")
    try:
        pending = transition(operator, ready, "dispatched")
        assert pending.status_code == 202, pending.text
        operation_id = pending.json()["operation_id"]
        database_script(compose, "orders", """
connection.execute(text(
    "UPDATE dispatch_operations SET attempts=9, next_attempt_at=now() WHERE id=:operation_id"
), parameters)
""", operation_id=operation_id)

        wait_for(
            lambda: operator.get(ORDERS + "/dispatches", params={"state": "needs_attention"}).json()["items"],
            lambda items: operation_id in [item["operation_id"] for item in items],
        )
        assert customer.get(ORDERS + "/dispatches").status_code == 401
        assert operator.post(ORDERS + "/dispatches/" + operation_id + "/resume").status_code == 403
        assert admin.post(ORDERS + "/dispatches/" + operation_id + "/resume", headers={"X-CSRF-Token": ""}).status_code == 403
        assert customer.get(ORDERS + "/orders/" + order["id"]).json()["dispatch_state"] == "needs_attention"
    finally:
        compose("up", "-d", "--no-deps", "--wait", "deliveries")

    resumed = admin.post(ORDERS + "/dispatches/" + operation_id + "/resume")
    assert resumed.status_code == 202, resumed.text
    assert admin.post(ORDERS + "/dispatches/" + operation_id + "/resume").status_code == 409
    wait_for(
        lambda: customer.get(ORDERS + "/orders/" + order["id"]).json(),
        lambda value: value["state"] == "dispatched",
    )

    audits = database_script(compose, "orders", """
print(connection.scalar(text("SELECT count(*) FROM dispatch_resumes WHERE operation_id=:operation_id"), parameters))
""", operation_id=operation_id)
    assert audits.splitlines()[-1] == "1"


def test_one_key_cannot_serve_a_transition_and_a_dispatch(delivery_shop):
    admin, operator, customer, _, product = delivery_shop
    received = confirmed(customer, create(customer, delivery_payload(admin, product)))
    ready = advance(operator, confirmed(customer, create(customer, delivery_payload(admin, product))), "preparing", "ready")
    key = str(uuid4())

    with ThreadPoolExecutor(max_workers=2) as pool:
        started = pool.submit(transition, operator, received, "preparing", key)
        dispatched = pool.submit(transition, operator, ready, "dispatched", key)
        responses = {"started": started.result(), "dispatched": dispatched.result()}

    statuses = sorted(response.status_code for response in responses.values())
    assert statuses == [200, 409], {name: response.text for name, response in responses.items()}

    states = {name: customer.get(ORDERS + "/orders/" + order["id"]).json() for name, order in
        [("started", received), ("dispatched", ready)]}
    expected = {"started": ("preparing", "received"), "dispatched": ("dispatched", "ready")}
    for name, (applied, untouched) in expected.items():
        assert states[name]["state"] == (applied if responses[name].status_code == 200 else untouched)
        assert states[name]["dispatch_state"] is None

    attention = operator.get(ORDERS + "/dispatches", params={"state": "needs_attention"}).json()["items"]
    assert ready["id"] not in [item["order_id"] for item in attention]
