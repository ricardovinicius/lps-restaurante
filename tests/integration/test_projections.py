import json
from uuid import uuid4

import pytest

from tests.integration.support import CATALOG, CONFIG, ORDERS, database_script


@pytest.fixture
def projection_shop(shop, request):
    admin, operator, customer, compose, product = shop
    configuration = admin.get(CONFIG).json()
    assert admin.put(CONFIG, json={
        "expected_revision": configuration["revision"],
        "features": {**configuration["features"], "tv": True},
    }).status_code == 200
    baseline = admin.get(ORDERS + "/summary").json()
    board = customer.get(ORDERS + "/tv").json()
    identifiers = []
    request.addfinalizer(lambda: remove_orders(compose, identifiers))
    rows = []
    for fulfillment, amount in [("pickup", 1000), ("delivery", 1500), ("table", 2000)]:
        states = ["received", "preparing", "ready", "completed"]
        if fulfillment == "delivery":
            states.append("dispatched")

        for state in states:
            identifier = str(uuid4())
            identifiers.append(identifier)
            rows.append({"id": identifier, "fulfillment": fulfillment, "state": state, "amount": amount})
    for _ in range(12):
        identifier = str(uuid4())
        identifiers.append(identifier)
        rows.append({"id": identifier, "fulfillment": "pickup", "state": "completed", "amount": 1000})
    output = database_script(compose, "orders", """
from datetime import UTC, datetime
from uuid import UUID, uuid4
from sqlalchemy import insert
from services.orders.models import Order
inserted = []
for row in parameters["rows"]:
    number = connection.scalar(insert(Order).values(
        id=UUID(row["id"]), origin="counter", fulfillment=row["fulfillment"],
        customer_name="Nome privado da TV", state=row["state"], version=1,
        configuration_revision=1, catalog_revision=1, fee_cents=500 if row["fulfillment"]=="delivery" else 0,
        total_cents=row["amount"], table_id=uuid4() if row["fulfillment"]=="table" else None,
        table_number=3 if row["fulfillment"]=="table" else None,
        created_at=datetime(2000, 1, 1, tzinfo=UTC),
    ).returning(Order.number))
    inserted.append({**row, "number": number})
print(json.dumps(inserted))
""", rows=rows)
    inserted = json.loads(output.splitlines()[-1])
    yield admin, operator, customer, compose, product, baseline, board, inserted


def remove_orders(compose, identifiers):
    database_script(compose, "orders", """
from uuid import UUID
from sqlalchemy import delete
from services.orders.models import Order
connection.execute(delete(Order).where(Order.id.in_([UUID(value) for value in parameters["ids"]])))
""", ids=identifiers)


def test_tv_projection_states_totals_cursors_and_privacy(projection_shop):
    admin, _, customer, _, _, _, baseline, rows = projection_shop
    response = customer.get(ORDERS + "/tv", params={"limit": 2})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    board = response.json()
    assert admin.get(ORDERS + "/tv", params={"limit": 2}).json() == board
    for state in ("preparing", "ready"):
        page = board[state]
        assert page["total"] == baseline[state]["total"] + 3
        assert len(page["items"]) == 2
        assert page["next_cursor"]
        collected = page["items"][:]
        cursor = page["next_cursor"]
        while cursor:
            following = customer.get(ORDERS + "/tv", params={state + "_cursor": cursor, "limit": 2}).json()[state]
            assert following["total"] == page["total"]
            collected.extend(following["items"])
            cursor = following["next_cursor"]
        assert len(collected) == page["total"]
        assert len({item["number"] for item in collected}) == len(collected)
        expected = {row["number"] for row in rows if row["state"] == state}
        assert expected <= {item["number"] for item in collected}
        assert not {row["number"] for row in rows if row["state"] not in ("preparing", "ready")} & {
            item["number"] for item in collected
        }
        assert all(set(item) == {"number", "fulfillment", "table_number"} for item in collected)
        assert any(item["table_number"] == 3 for item in collected if item["number"] in expected)

    assert customer.get(ORDERS + "/tv", params={"preparing_cursor": "invalid"}).status_code == 422
    assert customer.get(ORDERS + "/tv", params={"limit": 101}).status_code == 422
    last = customer.get(ORDERS + "/tv", params={"ready_cursor": board["ready"]["next_cursor"], "limit": 100}).json()
    assert last["ready"]["next_cursor"] is None


def test_summaries_are_admin_only_and_aggregate_all_history(projection_shop):
    admin, operator, customer, compose, _, baseline, _, _ = projection_shop
    summary = admin.get(ORDERS + "/summary")
    assert summary.status_code == 200
    assert summary.json() == {
        "active_orders": baseline["active_orders"] + 10,
        "completed_order_value_cents": baseline["completed_order_value_cents"] + 16500,
    }
    actual = json.loads(database_script(compose, "catalog", """
print(json.dumps(list(connection.execute(text(
    "SELECT count(*) FILTER (WHERE available), count(*) FROM products"
)).one())))
""").splitlines()[-1])
    assert admin.get(CATALOG + "/summary").json() == {
        "available_products": actual[0], "total_products": actual[1],
    }
    for path in (ORDERS + "/summary", CATALOG + "/summary"):
        assert customer.get(path).status_code == 401
        assert operator.get(path).status_code == 403
        assert admin.get(path).headers["cache-control"] == "no-store"


def test_tv_rechecks_configuration_and_does_not_need_optional_services(projection_shop):
    admin, _, customer, compose, _, _, _, _ = projection_shop
    configuration = admin.get(CONFIG).json()
    assert admin.put(CONFIG, json={
        "expected_revision": configuration["revision"],
        "features": {**configuration["features"], "tv": False},
    }).status_code == 200
    assert customer.get(ORDERS + "/tv").json()["error"]["code"] == "feature_disabled"
    configuration = admin.get(CONFIG).json()
    assert admin.put(CONFIG, json={
        "expected_revision": configuration["revision"],
        "features": {**configuration["features"], "tv": True},
    }).status_code == 200
    compose("stop", "tables", "deliveries")
    try:
        assert customer.get(ORDERS + "/tv").status_code == 200
        assert admin.get(ORDERS + "/summary").status_code == 200
    finally:
        compose("up", "-d", "--no-deps", "--wait", "tables", "deliveries")

    compose("stop", "configuration")
    try:
        unavailable = customer.get(ORDERS + "/tv")
        assert unavailable.status_code == 503
        assert unavailable.headers["retry-after"] == "3"
    finally:
        compose("up", "-d", "--no-deps", "--wait", "configuration")
