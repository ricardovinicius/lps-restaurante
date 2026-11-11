from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from mesa_platform.http import ApiError, Input, database_session
from mesa_platform.service_access import require_service_key
from services.catalog.models import CatalogRevision, Product, Quote

def require_orders_service(request: Request):
    require_service_key(request, "MESA_ORDERS_ACCESS_KEY")


router = APIRouter(prefix="/internal/v1", dependencies=[Depends(require_orders_service)])


class QuoteItemInput(Input):
    product_id: UUID
    quantity: int = Field(strict=True, ge=1, le=99)
    expected_unit_price_cents: int = Field(strict=True, gt=0, le=2147483647)


class QuoteInput(Input):
    expected_revision: int = Field(strict=True, gt=0, le=2147483647)
    items: list[QuoteItemInput] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def reject_duplicate_products(self):
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("Não repita produtos no mesmo pedido.")

        return self


class QuoteItem(BaseModel):
    product_id: UUID
    name: str
    unit_price_cents: int
    quantity: int
    subtotal_cents: int


class QuoteReceipt(BaseModel):
    catalog_revision: int
    items: list[QuoteItem]
    total_cents: int


@router.post("/quotes/{operation_id}", status_code=201, response_model=QuoteReceipt)
def quote(operation_id: UUID, payload: QuoteInput, response: Response, db=Depends(database_session)):
    revision = db.scalar(
        select(CatalogRevision.revision).where(CatalogRevision.id == 1).with_for_update()
    )
    if revision is None:
        raise ApiError(503, "catalog_unavailable", "Catálogo ainda não provisionado.")

    request_payload = payload.model_dump(mode="json")
    existing = db.get(Quote, operation_id)
    if existing is not None:
        if existing.request_payload != request_payload:
            raise ApiError(409, "idempotency_conflict", "A operação já foi utilizada com outros dados.")

        response.status_code = 200
        return QuoteReceipt.model_validate(existing.snapshot)

    if revision != payload.expected_revision:
        raise ApiError(409, "catalog_changed", "O catálogo foi alterado.", {"revision": revision})

    products = {
        product.id: product
        for product in db.scalars(select(Product).where(
            Product.id.in_([item.product_id for item in payload.items]),
        ))
    }
    items = []
    for item in payload.items:
        product = products.get(item.product_id)
        if product is None or not product.available:
            raise ApiError(409, "product_unavailable", "Um produto não está mais disponível.", {
                "product_id": str(item.product_id),
            })

        if product.price_cents != item.expected_unit_price_cents:
            raise ApiError(409, "price_changed", "O preço de um produto foi alterado.", {
                "product_id": str(item.product_id),
                "unit_price_cents": product.price_cents,
            })

        items.append(QuoteItem(
            product_id=product.id,
            name=product.name,
            unit_price_cents=product.price_cents,
            quantity=item.quantity,
            subtotal_cents=product.price_cents * item.quantity,
        ))

    receipt = QuoteReceipt(
        catalog_revision=revision,
        items=items,
        total_cents=sum(item.subtotal_cents for item in items),
    )
    db.add(Quote(
        operation_id=operation_id,
        request_payload=request_payload,
        snapshot=receipt.model_dump(mode="json"),
    ))
    db.commit()
    return receipt
