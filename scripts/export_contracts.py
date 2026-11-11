"""Export only implemented OpenAPI and the product schema, without connecting to DB."""

import json
from pathlib import Path

from mesa_platform.application import create_app
from mesa_platform.settings import Settings
from services.configuration.features import Product

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    settings = Settings(database_url="postgresql+psycopg://unused:unused@localhost/unused")

    for service in ["configuration", "catalog", "orders", "deliveries", "tables"]:
        spec = create_app(service, settings).openapi()
        path = ROOT / "docs/contracts" / f"health-{service}.json"
        path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")

    schema = ROOT / "products/schema/product.schema.json"
    schema.write_text(json.dumps(Product.model_json_schema(), indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
