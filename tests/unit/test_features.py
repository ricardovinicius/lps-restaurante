import itertools
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from services.configuration.features import Features, Product

ROOT = Path(__file__).resolve().parents[2]
KEYS = ["pickup", "delivery", "tables", "tablet", "tv"]


@pytest.mark.parametrize("values", list(itertools.product([False, True], repeat=5)))
def test_all_feature_combinations(values):
    data = dict(zip(KEYS, values))
    valid = any(values[:3]) and (not data["tablet"] or data["tables"])

    if not valid:
        with pytest.raises(ValidationError):
            Features(**data)
        return

    features = Features(**data)
    assert features.catalog is True
    assert features.orders is True
    assert ("deliveries" in features.required_services()) == data["delivery"]
    assert ("tables" in features.required_services()) == data["tables"]


@pytest.mark.parametrize("field,value", [
    ("pickup", "false"), ("delivery", 1), ("catalog", False),
    ("orders", False), ("unknown", True), ("catalog", 1), ("orders", "true"),
])
def test_rejects_ambiguous_or_unknown_features(field, value):
    data = dict(zip(KEYS, [True, False, False, False, True]))
    data[field] = value

    with pytest.raises(ValidationError):
        Features(**data)


def test_product_presets_and_schema():
    schema = json.loads((ROOT / "products/schema/product.schema.json").read_text())
    assert schema == Product.model_json_schema()
    Draft202012Validator.check_schema(schema)

    for path in (ROOT / "products").glob("*.json"):
        data = json.loads(path.read_text())
        Draft202012Validator(schema).validate(data)
        Product.model_validate(data)


def test_rejects_service_list_inconsistent_with_features():
    data = json.loads((ROOT / "products/delivery.json").read_text())
    data["services"].remove("deliveries")

    with pytest.raises(ValidationError, match="Serviços"):
        Product.model_validate(data)
