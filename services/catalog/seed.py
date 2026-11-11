import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert

from services.catalog.models import CatalogRevision, Category, Product


def demo_id(name):
    return uuid5(NAMESPACE_URL, f"https://mesa-facil.example/demo/{name}")


PRODUCTS = json.loads(Path(__file__).with_name("demo-products.json").read_text())


def seed(connection):
    connection.execute(insert(CatalogRevision).values(id=1, revision=1).on_conflict_do_nothing())

    for category in sorted({item["category"] for item in PRODUCTS}):
        connection.execute(insert(Category).values(
            id=demo_id(category), name=category,
        ).on_conflict_do_nothing())

    for item in PRODUCTS:
        connection.execute(insert(Product).values(
            id=demo_id(item["slug"]), category_id=demo_id(item["category"]),
            name=item["name"], description=item["description"],
            price_cents=item["price_cents"], image_url=item["image_url"], available=True,
        ).on_conflict_do_nothing())
