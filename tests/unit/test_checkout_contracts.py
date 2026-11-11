from uuid import UUID

import pytest
from pydantic import ValidationError

from services.catalog.internal import QuoteInput
from services.configuration.internal import AdmissionInput

PRODUCT_ID = "24a548d7-0135-4125-a4e4-dfb69c2c4064"
ITEM = {"product_id": PRODUCT_ID, "quantity": 2, "expected_unit_price_cents": 3290}
ADMISSION = {"principal": "customer:demo", "revision": 1, "origin": "client", "fulfillment": "pickup"}


def test_quote_accepts_quantity_and_price_boundaries():
    quote = QuoteInput.model_validate({
        "expected_revision": 2147483647,
        "items": [
            {**ITEM, "quantity": 1, "expected_unit_price_cents": 1},
            {**ITEM, "product_id": str(UUID(int=1)), "quantity": 99, "expected_unit_price_cents": 2147483647},
        ],
    })

    assert quote.items[0].product_id == UUID(PRODUCT_ID)
    assert quote.items[1].quantity == 99


@pytest.mark.parametrize("count", [1, 50])
def test_quote_accepts_item_count_boundaries(count):
    items = [{**ITEM, "product_id": str(UUID(int=index + 1))} for index in range(count)]

    assert len(QuoteInput.model_validate({"expected_revision": 1, "items": items}).items) == count


@pytest.mark.parametrize("count", [0, 51])
def test_quote_rejects_item_count_outside_limits(count):
    items = [{**ITEM, "product_id": str(UUID(int=index + 1))} for index in range(count)]

    with pytest.raises(ValidationError):
        QuoteInput.model_validate({"expected_revision": 1, "items": items})


def test_quote_rejects_duplicate_product_even_with_different_uuid_case():
    with pytest.raises(ValidationError, match="Não repita produtos"):
        QuoteInput.model_validate({
            "expected_revision": 1,
            "items": [ITEM, {**ITEM, "product_id": PRODUCT_ID.upper(), "quantity": 1}],
        })


@pytest.mark.parametrize("field,value", [
    ("quantity", 0), ("quantity", 100), ("quantity", True),
    ("quantity", "2"), ("quantity", 2.0),
    ("expected_unit_price_cents", 0), ("expected_unit_price_cents", -1),
    ("expected_unit_price_cents", 2147483648), ("expected_unit_price_cents", True),
    ("expected_unit_price_cents", "3290"), ("expected_unit_price_cents", 3290.0),
    ("product_id", "invalid"), ("product_id", None), ("product_id", True),
    ("subtotal_cents", 6580),
])
def test_quote_rejects_invalid_item_fields(field, value):
    with pytest.raises(ValidationError):
        QuoteInput.model_validate({"expected_revision": 1, "items": [{**ITEM, field: value}]})


@pytest.mark.parametrize("field,value", [
    ("expected_revision", 0), ("expected_revision", 2147483648),
    ("expected_revision", True), ("expected_revision", "1"), ("expected_revision", 1.0),
    ("items", None), ("total_cents", 6580),
])
def test_quote_rejects_invalid_revision_and_unknown_fields(field, value):
    with pytest.raises(ValidationError):
        QuoteInput.model_validate({"expected_revision": 1, "items": [ITEM], field: value})


@pytest.mark.parametrize("origin", ["client", "counter"])
def test_admission_accepts_pickup_origins(origin):
    admission = AdmissionInput.model_validate({**ADMISSION, "origin": origin})

    assert admission.origin == origin
    assert admission.fulfillment == "pickup"


@pytest.mark.parametrize("field,value", [
    ("principal", ""), ("principal", "x" * 201), ("principal", 1), ("principal", None),
    ("revision", 0), ("revision", 2147483648), ("revision", True),
    ("revision", "1"), ("revision", 1.0),
    ("origin", "tablet"), ("origin", "admin"), ("origin", True),
    ("fulfillment", "delivery"), ("fulfillment", "tables"), ("fulfillment", False),
    ("configuration_revision", 1),
])
def test_admission_rejects_invalid_and_ambiguous_fields(field, value):
    with pytest.raises(ValidationError):
        AdmissionInput.model_validate({**ADMISSION, field: value})


@pytest.mark.parametrize("field", ["principal", "revision", "origin", "fulfillment"])
def test_admission_requires_complete_identity_and_context(field):
    payload = {key: value for key, value in ADMISSION.items() if key != field}

    with pytest.raises(ValidationError):
        AdmissionInput.model_validate(payload)
