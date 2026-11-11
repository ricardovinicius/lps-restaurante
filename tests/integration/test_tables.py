"""Table orders and the tablet Comanda across Mesas, Pedidos, Configuração and Catálogo."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import time
from uuid import uuid4

import httpx
import pytest

from tests.integration.support import (
    CONFIG, ORDERS, SESSIONS, confirmed, create, database_script, payload_for, sign_in, transition,
)

TABLES = "/api/tables/v1"
REQUEST_ID = "00000000-0000-4000-8000-000000000002"


def set_features(admin, **features):
    current = admin.get(CONFIG).json()
    response = admin.put(CONFIG, json={
        "expected_revision": current["revision"], "features": {**current["features"], **features},
    })
    assert response.status_code == 200, response.text


def all_tables(operator):
    items = operator.get(TABLES + "/tables", params={"include_unavailable": "true", "limit": 100}).json()["items"]
    return {table["number"]: table for table in items}


def set_available(operator, number, available):
    table = all_tables(operator)[number]
    if table["available"] == available:
        return table

    response = operator.patch(TABLES + "/tables/" + table["id"], json={
        "expected_version": table["version"], "available": available,
    })
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def table_shop(shop, deployment):
    admin, operator, customer, compose, product = shop
    set_features(admin, tables=True, tablet=True)
    for number in range(1, 13):
        set_available(operator, number, True)

    yield admin, operator, customer, compose, product, deployment


def table_payload(admin, product, table, **changes):
    return payload_for(admin, product, fulfillment="table", table_id=table["id"], **changes)


def tablet_payload(admin, product):
    payload = payload_for(admin, product, origin="tablet", fulfillment="table")
    del payload["customer_name"]
    return payload


def provision(deployment, table, *, logout=True):
    """Bind a fresh browser to a table as an operator, then leave the staff account."""
    base, passwords, _ = deployment
    client = httpx.Client(base_url=base, timeout=15)
    sign_in(client, passwords, "operator")
    response = client.post(TABLES + "/table-contexts", json={"table_id": table["id"]})
    assert response.status_code == 201, response.text

    if logout:
        assert client.delete(SESSIONS + "/current").status_code == 204
        del client.headers["X-CSRF-Token"]

    return client, response.json()


def send_round(tablet, context, payload, key=None, *, context_id=None):
    return tablet.post(ORDERS + "/orders", json=payload, headers={
        "Idempotency-Key": key or str(uuid4()),
        "X-CSRF-Token": context["csrf_token"],
        "X-Table-Context": context_id or context["context_id"],
    })


def history(tablet, **params):
    return tablet.get(ORDERS + "/table-orders", params=params)


def wait_for(read, accept, timeout=25):
    deadline = time.monotonic() + timeout
    value = read()
    while not accept(value) and time.monotonic() < deadline:
        time.sleep(0.3)
        value = read()

    assert accept(value), value
    return value


def postpone_retries(compose, operation_id):
    def update():
        output = database_script(compose, "orders", """
result = connection.execute(text(
    "UPDATE checkout_operations SET next_attempt_at=now() + interval '1 hour' "
    "WHERE id=:operation_id AND lease_id IS NULL"
), parameters)
print(result.rowcount)
""", operation_id=operation_id)
        return output.splitlines()[-1]

    wait_for(update, lambda count: count == "1")


def test_listing_availability_and_provisioning_rules(table_shop):
    admin, operator, customer, _, _, deployment = table_shop
    public = customer.get(TABLES + "/tables", params={"limit": 100}).json()["items"]
    assert sorted(table["number"] for table in public) == list(range(1, 13))
    assert customer.get(TABLES + "/tables", params={"include_unavailable": "true"}).status_code == 401

    table = all_tables(operator)[11]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda available: operator.patch(TABLES + "/tables/" + table["id"], json={
            "expected_version": table["version"], "available": available,
        }), [False, False]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert 11 not in [item["number"] for item in customer.get(TABLES + "/tables", params={"limit": 100}).json()["items"]]

    assert customer.post(TABLES + "/table-contexts", json={"table_id": table["id"]}).status_code == 401
    no_csrf = operator.post(TABLES + "/table-contexts", json={"table_id": table["id"]}, headers={"X-CSRF-Token": ""})
    assert no_csrf.status_code == 403
    unavailable = operator.post(TABLES + "/table-contexts", json={"table_id": table["id"]})
    assert unavailable.status_code == 409, unavailable.text

    set_features(admin, tablet=False)
    disabled = operator.post(TABLES + "/table-contexts", json={"table_id": all_tables(operator)[10]["id"]})
    assert disabled.json()["error"]["code"] == "feature_disabled"
    set_features(admin, tables=False)
    assert customer.get(TABLES + "/tables").json()["error"]["code"] == "feature_disabled"
    assert operator.get(TABLES + "/tables", params={"include_unavailable": "true"}).status_code == 200


def test_orders_from_every_origin_share_the_table_history(table_shop):
    admin, operator, customer, compose, product, deployment = table_shop
    tables = all_tables(operator)
    table_a, table_b = tables[1], tables[2]

    from_client = confirmed(customer, create(customer, table_payload(admin, product, table_a)))
    assert (from_client["table_number"], from_client["fee_cents"], from_client["origin"]) == (1, 0, "client")
    from_counter = confirmed(operator, create(operator, table_payload(admin, product, table_a, origin="counter")))
    assert from_counter["table_number"] == 1

    tablet, context = provision(deployment, table_a)
    with closing(tablet):
        current = tablet.get(TABLES + "/table-contexts/current").json()
        assert (current["context_id"], current["table_number"]) == (context["context_id"], 1)

        payload = tablet_payload(admin, product)
        key = str(uuid4())
        first = confirmed(tablet, send_round(tablet, context, payload, key))
        second = confirmed(tablet, send_round(tablet, context, payload))
        assert first["number"] != second["number"]
        assert (first["origin"], first["table_number"], first["customer_name"]) == ("tablet", 1, None)
        assert confirmed(tablet, send_round(tablet, context, payload, key))["id"] == first["id"]

        with_name = send_round(tablet, context, {**payload, "customer_name": "Intruso"})
        assert with_name.status_code == 422
        with_table = send_round(tablet, context, {**payload, "table_id": table_b["id"]})
        assert with_table.status_code == 422
        changed = send_round(tablet, context, payload, context_id=str(uuid4()))
        assert changed.json()["error"]["code"] == "table_context_changed"
        no_csrf = tablet.post(ORDERS + "/orders", json=payload, headers={
            "Idempotency-Key": str(uuid4()), "X-Table-Context": context["context_id"],
        })
        assert no_csrf.status_code == 403
        assert tablet.get(ORDERS + "/queue").status_code == 401

        done = first
        for state in ("preparing", "ready", "completed"):
            done = transition(operator, done, state).json()
        assert done["state"] == "completed"

        page = history(tablet).json()
        orders = [from_client, from_counter, first, second]
        assert page["table"]["number"] == 1
        assert page["order_count"] == 4
        assert page["historical_total_cents"] == sum(order["total_cents"] for order in orders)
        assert [item["id"] for item in page["items"]] == [order["id"] for order in reversed(orders)]
        assert {item["customer_name"] for item in page["items"]} == {None}
        assert {item["state"] for item in page["items"] if item["id"] == first["id"]} == {"completed"}

        limited = history(tablet, limit=3).json()
        rest = history(tablet, limit=3, cursor=limited["next_cursor"]).json()
        assert [item["id"] for item in limited["items"] + rest["items"]] == [item["id"] for item in page["items"]]
        assert rest["historical_total_cents"] == page["historical_total_cents"]

        tablet_b, context_b = provision(deployment, table_b)
        with closing(tablet_b):
            empty = history(tablet_b).json()
            assert (empty["items"], empty["order_count"], empty["historical_total_cents"]) == ([], 0, 0)
            assert tablet_b.get(ORDERS + "/orders/" + first["id"]).status_code == 404
        single = tablet.get(ORDERS + "/orders/" + from_client["id"])
        assert single.status_code == 200
        assert single.json()["customer_name"] is None
        assert operator.get(ORDERS + "/orders/" + from_client["id"]).json()["customer_name"] == from_client["customer_name"]

    queue = operator.get(ORDERS + "/queue", params={"fulfillment": "table", "limit": 100}).json()["items"]
    assert {second["id"], from_client["id"]} <= {item["id"] for item in queue}
    with httpx.Client(base_url=deployment[0]) as stranger:
        assert stranger.get(ORDERS + "/table-orders").status_code == 401
        assert stranger.get(ORDERS + "/orders/" + second["id"]).status_code == 404


def test_unavailable_tables_and_disabled_features_block_only_new_orders(table_shop):
    admin, operator, customer, _, product, deployment = table_shop
    tables = all_tables(operator)

    set_available(operator, 3, False)
    rejected = create(customer, table_payload(admin, product, tables[3]))
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error"]["code"] == "table_unavailable"
    assert customer.get(ORDERS + "/my-orders").json()["items"] == []

    accepted = confirmed(customer, create(customer, table_payload(admin, product, tables[4])))
    set_available(operator, 4, False)
    assert transition(operator, accepted, "preparing").status_code == 200
    set_available(operator, 4, True)

    tablet, context = provision(deployment, tables[4])
    with closing(tablet):
        payload = tablet_payload(admin, product)
        set_features(admin, tablet=False)
        blocked = send_round(tablet, context, {**payload, "configuration_revision": admin.get(CONFIG).json()["revision"]})
        assert blocked.json()["error"]["code"] == "feature_disabled"

        set_features(admin, tables=False)
        blocked = create(customer, table_payload(admin, product, tables[5]))
        assert blocked.json()["error"]["code"] == "feature_disabled"
        assert history(tablet).json()["order_count"] == 1
        assert customer.get(ORDERS + "/orders/" + accepted["id"]).json()["state"] == "preparing"

    current = customer.get(ORDERS + "/orders/" + accepted["id"]).json()
    for state in ("ready", "completed"):
        current = transition(operator, current, state).json()
    assert current["state"] == "completed"


def test_validation_recovers_after_lost_response_and_restart(table_shop):
    admin, operator, customer, compose, product, deployment = table_shop
    table = all_tables(operator)[5]
    payload = table_payload(admin, product, table)
    key = str(uuid4())
    tablet, context = provision(deployment, table)

    compose("stop", "tables")
    try:
        pending = create(customer, payload, key)
        assert pending.status_code == 202, pending.text
        operation_id = pending.json()["operation_id"]
        assert history(tablet).status_code == 503
        postpone_retries(compose, operation_id)
    finally:
        compose("up", "-d", "--no-deps", "--wait", "tables")

    # Mesas commits the receipt, but Pedidos never sees the response.
    database_script(compose, "orders", """
from services.orders.dependencies import validate_table
row = connection.execute(text(
    "SELECT id, payload FROM checkout_operations WHERE id=:operation_id"
), parameters).one()
validate_table(row, parameters["request_id"])
""", operation_id=operation_id, request_id=REQUEST_ID)

    compose("up", "-d", "--force-recreate", "--no-deps", "--wait", "orders")
    database_script(compose, "orders", """
connection.execute(text("UPDATE checkout_operations SET next_attempt_at=now() WHERE id=:operation_id"), parameters)
""", operation_id=operation_id)

    status = wait_for(
        lambda: customer.get(ORDERS + "/operations/" + operation_id).json(),
        lambda value: value["state"] == "succeeded",
    )
    assert status["order"]["table_number"] == 5
    assert confirmed(customer, create(customer, payload, key))["id"] == status["order"]["id"]
    receipts = database_script(compose, "tables", """
print(connection.scalar(text("SELECT count(*) FROM table_validations WHERE operation_id=:operation_id"), parameters))
""", operation_id=operation_id)
    assert receipts.splitlines()[-1] == "1"
    with closing(tablet):
        assert history(tablet).json()["order_count"] == 1


def test_same_operation_cannot_validate_two_tables(table_shop):
    _, operator, _, compose, _, _ = table_shop
    tables = all_tables(operator)
    output = database_script(compose, "orders", """
from types import SimpleNamespace
from uuid import uuid4
from mesa_platform.http import ApiError
from services.orders.dependencies import validate_table
operation_id = uuid4()
first = validate_table(SimpleNamespace(id=operation_id, payload={"table_id": parameters["first"]}), parameters["request_id"])
replay = validate_table(SimpleNamespace(id=operation_id, payload={"table_id": parameters["first"]}), parameters["request_id"])
try:
    validate_table(SimpleNamespace(id=operation_id, payload={"table_id": parameters["second"]}), parameters["request_id"])
except ApiError as error:
    conflict = [error.status, error.code]
print(json.dumps([first == replay, conflict]))
""", first=tables[7]["id"], second=tables[8]["id"], request_id=REQUEST_ID)
    assert json.loads(output.splitlines()[-1]) == [True, [409, "idempotency_conflict"]]


def test_tablet_round_finishes_after_credential_expires(table_shop):
    admin, operator, _, compose, product, deployment = table_shop
    table = all_tables(operator)[6]
    tablet, context = provision(deployment, table)
    payload = tablet_payload(admin, product)
    key = str(uuid4())

    with closing(tablet):
        compose("stop", "catalog")
        try:
            pending = send_round(tablet, context, payload, key)
            assert pending.status_code == 202, pending.text
            assert pending.json()["state"] == "pending"
            database_script(compose, "tables", """
connection.execute(text(
    "UPDATE table_contexts SET expires_at=now() - interval '1 minute' WHERE id=:context_id"
), parameters)
""", context_id=context["context_id"])
        finally:
            compose("up", "-d", "--no-deps", "--wait", "catalog")

        assert tablet.get(TABLES + "/table-contexts/current").status_code == 401
        assert history(tablet).status_code == 401

    found = wait_for(
        lambda: operator.get(ORDERS + "/operations", params={"reference": key}).json()["items"],
        lambda items: items and items[0]["state"] == "succeeded",
    )
    assert (found[0]["origin"], found[0]["customer_name"], found[0]["table_number"]) == ("tablet", None, 6)


def test_operator_reads_orders_while_mesas_is_down_even_with_a_tablet_cookie(table_shop):
    admin, operator, customer, compose, product, deployment = table_shop
    table = all_tables(operator)[10]
    order = confirmed(customer, create(customer, table_payload(admin, product, table)))
    staff_tablet, _ = provision(deployment, table, logout=False)
    tablet, _ = provision(deployment, table)

    with closing(staff_tablet), closing(tablet):
        compose("stop", "tables")
        try:
            as_staff = staff_tablet.get(ORDERS + "/orders/" + order["id"])
            assert as_staff.status_code == 200, as_staff.text
            assert as_staff.json()["customer_name"] == order["customer_name"]
            assert tablet.get(ORDERS + "/orders/" + order["id"]).status_code == 503
        finally:
            compose("up", "-d", "--no-deps", "--wait", "tables")
