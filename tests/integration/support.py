"""HTTP and database helpers shared by the integration suites."""

import json
from textwrap import dedent, indent
import time
from uuid import uuid4

import pytest

CONFIG = "/api/configuration/v1/configuration"
SESSIONS = "/api/configuration/v1/sessions"
CATALOG = "/api/catalog/v1"
ORDERS = "/api/orders/v1"


def sign_in(client, passwords, user):
    assert client.post(SESSIONS, json={"username": user, "password": passwords[user]}).status_code == 201
    client.headers["X-CSRF-Token"] = client.get(SESSIONS + "/current").json()["csrf_token"]


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
