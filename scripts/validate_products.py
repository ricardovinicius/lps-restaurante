"""Validate product definitions before using them for derivation."""

from pathlib import Path

from services.configuration.features import Product

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for path in sorted((ROOT / "products").glob("*.json")):
        product = Product.model_validate_json(path.read_text())
        print(f"{path.name}: válido ({', '.join(product.services)})")


if __name__ == "__main__":
    main()
