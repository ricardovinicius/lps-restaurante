from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
from textwrap import dedent, indent
import time
import secrets
from uuid import uuid4

import httpx
import pytest

CONFIG = "/api/configuration/v1/configuration"
SESSIONS = "/api/configuration/v1/sessions"
CATALOG = "/api/catalog/v1"
ORDERS = "/api/orders/v1"


def sign_in(client, passwords, user):
    assert client.post(SESSIONS, json={"username": user, "password": passwords[user]}).status_code == 201
    client.headers["X-CSRF-Token"] = client.get(SESSIONS + "/current").json()["csrf_token"]


@pytest.fixture
def shop(deployment):
    base, passwords, compose = deployment
    with ExitStack() as stack:
        admin, operator, customer = [
            stack.enter_context(httpx.Client(base_url=base, timeout=15)) for _ in range(3)
        ]
        sign_in(admin, passwords, "admin")
        sign_in(operator, passwords, "operator")
        current = admin.get(CONFIG).json()
        response = admin.put(CONFIG, json={
            "expected_revision": current["revision"],
            "features": {**current["features"], "pickup": True},
        })
        assert response.status_code == 200, response.text
        catalog = admin.get(CATALOG + "/admin/products").json()
        product = catalog["items"][0]
        response = admin.patch(CATALOG + "/products/" + product["id"], json={
            "expected_revision": catalog["revision"], "available": True, "price_cents": 3290,
        })
        assert response.status_code == 200, response.text
        assert customer.post(ORDERS + "/customer-contexts").status_code == 201
        yield admin, operator, customer, compose, response.json()["product"]


def payload_for(admin, product, **changes):
    return {
        "configuration_revision": admin.get(CONFIG).json()["revision"],
        "catalog_revision": admin.get(CATALOG + "/products").json()["revision"],
        "origin": "client",
        "fulfillment": "pickup",
        "customer_name": "Cliente de teste",
        "items": [{
            "product_id": product["id"], "quantity": 2,
            "expected_unit_price_cents": product["price_cents"],
        }],
        **changes,
    }


def create(client, payload, key=None):
    return client.post(ORDERS + "/orders", json=payload, headers={"Idempotency-Key": key or str(uuid4())})


def confirmed(client, response):
    if response.status_code == 201:
        return response.json()
    assert response.status_code == 202, response.text
    operation = response.json()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        status = client.get(ORDERS + "/operations/" + operation["operation_id"])
        assert status.status_code == 200, status.text
        if status.json()["state"] == "succeeded":
            return status.json()["order"]
        assert status.json()["state"] == "pending", status.text
        time.sleep(0.2)
    pytest.fail("Pedido não foi confirmado após recuperação")


def transition(operator, order, state, key=None):
    return operator.post(ORDERS + "/orders/" + order["id"] + "/transitions", json={
        "expected_version": order["version"], "target_state": state,
    }, headers={"Idempotency-Key": key or str(uuid4())})


def database_script(compose, service, source, **parameters):
    bootstrap = f"""
import json
from sqlalchemy import text
from mesa_platform.database import create_database_engine
from mesa_platform.settings import Settings

parameters = json.loads({json.dumps(parameters)!r})
engine = create_database_engine(Settings())
try:
    with engine.begin() as connection:
{indent(dedent(source).strip(), "        ")}
finally:
    engine.dispose()
"""
    return compose("exec", "-T", service, "python", "-c", bootstrap)


def test_pickup_lifecycle_snapshots_and_customer_isolation(shop, deployment):
    admin, operator, customer, compose, product = shop
    payload = payload_for(admin, product)
    key = str(uuid4())
    order = confirmed(customer, create(customer, payload, key))
    assert order["state"] == "received"
    assert order["fee_cents"] == 0
    assert order["total_cents"] == product["price_cents"] * 2
    assert order["items"][0]["name"] == product["name"]
    assert order["number"] > 0
    assert confirmed(customer, create(customer, payload, key))["id"] == order["id"]
    assert create(customer, {**payload, "customer_name": "Outro nome"}, key).status_code == 409
    assert customer.get(ORDERS + "/my-orders").json()["items"][0]["id"] == order["id"]
    token = customer.cookies["mesa_customer"]
    customer.post(ORDERS + "/customer-contexts")
    assert customer.cookies["mesa_customer"] == token

    with httpx.Client(base_url=deployment[0]) as other:
        other.post(ORDERS + "/customer-contexts")
        assert other.get(ORDERS + "/orders/" + order["id"]).status_code == 404
        assert other.get(ORDERS + "/my-orders").json()["items"] == []
        assert other.get(ORDERS + "/queue").status_code == 401

    catalog = admin.get(CATALOG + "/admin/products").json()
    assert admin.patch(CATALOG + "/products/" + product["id"], json={
        "expected_revision": catalog["revision"], "price_cents": product["price_cents"] + 100,
    }).status_code == 200
    replay = confirmed(customer, create(customer, payload, key))
    assert replay["items"] == order["items"]
    assert replay["total_cents"] == order["total_cents"]
    assert transition(operator, order, "ready").status_code == 409
    first_key = str(uuid4())
    preparing = transition(operator, order, "preparing", first_key)
    assert preparing.status_code == 200, preparing.text
    ready = transition(operator, preparing.json(), "ready")
    assert ready.status_code == 200, ready.text
    replay = transition(operator, order, "preparing", first_key)
    assert replay.status_code == 200
    assert replay.json() == preparing.json()
    assert transition(operator, order, "preparing").status_code == 409

    current = admin.get(CONFIG).json()
    changed = admin.put(CONFIG, json={
        "expected_revision": current["revision"],
        "features": {**current["features"], "pickup": False, "delivery": True},
    })
    assert changed.status_code == 200
    blocked = create(customer, payload_for(admin, product))
    assert blocked.status_code == 403, blocked.text
    completed = transition(operator, ready.json(), "completed")
    assert completed.status_code == 200, completed.text
    assert customer.get(ORDERS + "/orders/" + order["id"]).json()["state"] == "completed"
    assert order["id"] not in [item["id"] for item in operator.get(ORDERS + "/queue").json()["items"]]

    database_script(compose, "orders", """
assert connection.scalar(text(
    "SELECT count(*) FROM transitions WHERE order_id=:order_id"
), parameters) == 3
""", order_id=order["id"])


def test_checkout_rejects_invalid_unaccepted_and_unavailable_items(shop):
    admin, operator, customer, _, product = shop
    payload = payload_for(admin, product)
    for change in [
        {"customer_name": "   "}, {"items": []}, {"total_cents": 1},
        {"items": payload["items"] * 2},
        {"items": [{**payload["items"][0], "quantity": 0}]},
        {"items": [{**payload["items"][0], "quantity": 100}]},
        {"items": [{**payload["items"][0], "quantity": True}]},
        {"fulfillment": "delivery"},
    ]:
        response = create(customer, {**payload, **change})
        assert response.status_code == 422, response.text
    assert customer.post(ORDERS + "/orders", json=payload).status_code == 422
    assert create(customer, {**payload, "origin": "counter"}).status_code == 401
    assert create(admin, {**payload, "origin": "counter"}).status_code == 403
    no_csrf = operator.post(ORDERS + "/orders", json={**payload, "origin": "counter"}, headers={
        "Idempotency-Key": str(uuid4()), "X-CSRF-Token": "",
    })
    assert no_csrf.status_code == 403
    price_change = {**payload["items"][0], "expected_unit_price_cents": product["price_cents"] + 1}
    assert create(customer, {**payload, "items": [price_change]}).status_code == 409
    assert create(customer, {**payload, "configuration_revision": payload["configuration_revision"] - 1}).status_code == 409

    catalog = admin.get(CATALOG + "/admin/products").json()
    updated = admin.patch(CATALOG + "/products/" + product["id"], json={
        "expected_revision": catalog["revision"], "available": False,
    }).json()
    assert create(customer, payload).status_code == 409
    assert create(customer, {**payload, "catalog_revision": updated["revision"]}).status_code == 409
    assert customer.get(ORDERS + "/my-orders").json()["items"] == []


def test_concurrent_creation_and_transition_are_applied_once(shop):
    admin, operator, customer, _, product = shop
    payload = payload_for(admin, product)
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: create(customer, payload, key), range(2)))
    orders = [confirmed(customer, response) for response in responses]
    assert orders[0]["id"] == orders[1]["id"]
    assert len(customer.get(ORDERS + "/my-orders").json()["items"]) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: transition(operator, orders[0], "preparing"), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    preparing = next(response.json() for response in responses if response.status_code == 200)
    transition_key = str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: transition(operator, preparing, "ready", transition_key), range(2)))
    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()

    second = confirmed(customer, create(customer, payload))
    page = customer.get(ORDERS + "/my-orders", params={"limit": 1}).json()
    next_page = customer.get(ORDERS + "/my-orders", params={"limit": 1, "cursor": page["next_cursor"]}).json()
    assert {page["items"][0]["id"], next_page["items"][0]["id"]} == {orders[0]["id"], second["id"]}
    assert customer.get(ORDERS + "/my-orders", params={"cursor": "invalid"}).status_code == 422
    operational = confirmed(operator, create(operator, {**payload, "origin": "counter"}))
    assert operational["origin"] == "counter"
    assert customer.get(ORDERS + "/orders/" + operational["id"]).status_code == 404


def test_pending_creation_recovers_after_restart_and_configuration_change(shop):
    admin, operator, customer, compose, product = shop
    payload = payload_for(admin, product)
    key = str(uuid4())
    compose("stop", "catalog")
    try:
        pending = create(customer, payload, key)
        assert pending.status_code == 202, pending.text
        operation_id = pending.json()["operation_id"]
        database_script(compose, "orders", """
connection.execute(text(
    "UPDATE checkout_operations SET admission=NULL WHERE id=:operation_id"
), parameters)
""", operation_id=operation_id)
        current = admin.get(CONFIG).json()
        assert admin.put(CONFIG, json={
            "expected_revision": current["revision"],
            "features": {**current["features"], "pickup": False, "delivery": True},
        }).status_code == 200
        compose("up", "-d", "--force-recreate", "--no-deps", "--wait", "orders")
    finally:
        compose("start", "catalog")
    deadline = time.monotonic() + 25
    order = None
    while time.monotonic() < deadline:
        status = customer.get(ORDERS + "/operations/" + operation_id)
        if status.status_code == 200 and status.json()["state"] == "succeeded":
            order = status.json()["order"]
            break
        time.sleep(0.5)
    assert order is not None, status.text
    assert order["configuration_revision"] == payload["configuration_revision"]
    assert confirmed(customer, create(customer, payload, key))["id"] == order["id"]
    assert len(customer.get(ORDERS + "/my-orders").json()["items"]) == 1
    assert operator.get(ORDERS + "/orders/" + order["id"]).status_code == 200

    compose("up", "-d", "--force-recreate", "--no-deps", "--wait", "orders", "configuration", "catalog")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = customer.get(ORDERS + "/orders/" + order["id"])
        if response.status_code == 200:
            break
        time.sleep(0.5)
    assert response.json()["items"] == order["items"]
    assert response.json()["total_cents"] == order["total_cents"]


def test_large_valid_price_uses_exact_bigint_totals(shop):
    admin, _, customer, _, product = shop
    catalog = admin.get(CATALOG + "/admin/products").json()
    response = admin.patch(CATALOG + "/products/" + product["id"], json={
        "expected_revision": catalog["revision"], "price_cents": 2147483647,
    })
    assert response.status_code == 200
    updated_product = response.json()["product"]
    order = confirmed(customer, create(customer, payload_for(admin, updated_product)))
    assert order["total_cents"] == 4294967294
    assert order["items"][0]["subtotal_cents"] == 4294967294


def test_exhausted_operation_requires_authorized_audited_resume(shop):
    admin, operator, customer, compose, product = shop
    payload = payload_for(admin, product)
    compose("stop", "catalog")
    try:
        pending = create(customer, payload)
        assert pending.status_code == 202, pending.text
        operation_id = pending.json()["operation_id"]
        path = ORDERS + "/operations/" + operation_id
        database_script(compose, "orders", """
connection.execute(text(
    "UPDATE checkout_operations SET attempts=9, next_attempt_at=now() WHERE id=:operation_id"
), parameters)
""", operation_id=operation_id)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status = customer.get(path)
            if status.json()["state"] == "needs_attention":
                break
            time.sleep(0.2)
        assert status.json()["state"] == "needs_attention"
        assert operator.post(path + "/resume").status_code == 403
        assert admin.post(path + "/resume", headers={"X-CSRF-Token": ""}).status_code == 403
        assert customer.get(ORDERS + "/my-orders").json()["items"] == []
    finally:
        compose("start", "catalog")
    assert admin.post(path + "/resume").status_code == 200
    assert admin.post(path + "/resume").status_code == 409
    confirmed(customer, pending)
    database_script(compose, "orders", """
assert connection.scalar(text(
    "SELECT count(*) FROM operation_resumes WHERE operation_id=:operation_id"
), parameters) == 1
""", operation_id=operation_id)


def test_internal_auth_failure_is_recoverable_and_staff_can_find_it(shop, tmp_path):
    admin, operator, customer, compose, product = shop
    payload = payload_for(admin, product)
    reference = str(uuid4())
    override = tmp_path / "wrong-key.yaml"
    override.write_text("services:\n  catalog:\n    environment:\n      MESA_ORDERS_ACCESS_KEY: incorrect-test-key\n")
    compose("-f", "compose.yaml", "-f", str(override), "up", "-d", "--no-deps", "--force-recreate", "--wait", "catalog")
    try:
        pending = create(customer, payload, reference)
        assert pending.status_code == 202, pending.text
        path = ORDERS + "/operations/" + pending.json()["operation_id"]
        status = customer.get(path).json()
        assert status["state"] == "pending"
        assert status["error"]["code"] == "dependency_authentication_failed"
        assert customer.get(ORDERS + "/operations").status_code == 401
        for staff in (admin, operator):
            found = staff.get(ORDERS + "/operations", params={"reference": reference}).json()
            assert found["items"][0]["operation_id"] == pending.json()["operation_id"]
            assert staff.get(path).status_code == 200
        assert operator.post(path + "/resume").status_code == 403
        assert create(customer, payload, reference).status_code == 202
    finally:
        compose("up", "-d", "--no-deps", "--force-recreate", "--wait", "catalog")
    order = confirmed(customer, pending)
    assert confirmed(customer, create(customer, payload, reference))["id"] == order["id"]
    assert len(customer.get(ORDERS + "/my-orders").json()["items"]) == 1


def test_customer_cookie_recovery_preserves_identity_and_replay(shop):
    admin, operator, customer, _, product = shop
    recovery_token = secrets.token_hex(32)
    context = customer.post(ORDERS + "/customer-contexts", json={"recovery_token": recovery_token}).json()
    payload = payload_for(admin, product)
    reference = str(uuid4())
    order = confirmed(customer, create(customer, payload, reference))
    customer.cookies.clear()
    assert customer.get(ORDERS + "/orders/" + order["id"]).status_code == 404
    assert customer.post(ORDERS + "/customer-contexts/recover", json={
        "context_id": context["context_id"], "recovery_token": secrets.token_hex(32),
    }).status_code == 401
    recovered = customer.post(ORDERS + "/customer-contexts/recover", json={
        **context, "recovery_token": recovery_token,
    })
    assert recovered.status_code == 200, recovered.text
    assert recovered.json() == context
    assert "HttpOnly" in recovered.headers["Set-Cookie"]
    assert confirmed(customer, create(customer, payload, reference))["id"] == order["id"]
    customer.post(ORDERS + "/customer-contexts", json={"new_context": True})
    mismatched = customer.post(ORDERS + "/orders", json=payload, headers={
        "Idempotency-Key": reference, "X-Customer-Context": context["context_id"],
    })
    assert mismatched.status_code == 401
    assert customer.get(ORDERS + "/my-orders").json()["items"] == []
    assert customer.get(ORDERS + "/orders/" + order["id"]).status_code == 404
    found = operator.get(ORDERS + "/operations", params={"reference": reference}).json()["items"][0]
    assert admin.get(ORDERS + "/operations/" + found["operation_id"]).json()["order"]["id"] == order["id"]


def test_active_history_filters_and_batched_item_reads(shop):
    admin, operator, customer, compose, product = shop
    payload = payload_for(admin, product)
    first = confirmed(customer, create(customer, payload))
    second = confirmed(customer, create(customer, payload))
    for target in ("preparing", "ready", "completed"):
        response = transition(operator, first, target)
        assert response.status_code == 200
        first = response.json()
    active = customer.get(ORDERS + "/my-orders", params={"status": "active"}).json()
    completed = customer.get(ORDERS + "/my-orders", params={"status": "completed"}).json()
    assert [item["id"] for item in active["items"]] == [second["id"]]
    assert [item["id"] for item in completed["items"]] == [first["id"]]
    database_script(compose, "orders", """
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from services.orders.models import Order
from services.orders.views import order_page

queries = []
connection.exec_driver_sql('SELECT 1')
event.listen(engine, 'before_cursor_execute', lambda c, cu, statement, p, context, many: queries.append(statement))
with Session(engine) as db:
    page = order_page(db, select(Order), None, 100)
    assert len(page.items) >= 2
    assert len(queries) == 2, queries
""")


def test_upgrade_reclassifies_only_legacy_internal_auth_rejections(shop):
    admin, _, customer, compose, product = shop
    payload = payload_for(admin, product)
    payload["catalog_revision"] += 1
    legacy_key, business_key = str(uuid4()), str(uuid4())
    assert create(customer, payload, legacy_key).status_code == 409
    assert create(customer, payload, business_key).status_code == 409
    database_script(compose, "orders", """
from alembic import command
from mesa_platform.migrations import migration_config

config = migration_config('orders')
config.attributes['connection'] = connection
command.downgrade(config, 'orders_0002')
connection.execute(text(
    "UPDATE checkout_operations SET error_status=403, "
    "error=json_build_object('code','forbidden','message','Serviço não autorizado.','details',NULL) "
    "WHERE idempotency_key=:key"
), {'key': parameters['legacy_key']})
command.upgrade(config, 'head')
legacy = connection.execute(text(
    'SELECT state, error FROM checkout_operations WHERE idempotency_key=:key'
), {'key': parameters['legacy_key']}).one()
business = connection.scalar(text(
    'SELECT state FROM checkout_operations WHERE idempotency_key=:key'
), {'key': parameters['business_key']})
assert legacy.state == 'needs_attention'
assert legacy.error['code'] == 'dependency_authentication_failed'
assert business == 'rejected'
""", legacy_key=legacy_key, business_key=business_key)
