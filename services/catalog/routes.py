import base64
import binascii
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update

from mesa_platform.access import authorize_staff
from mesa_platform.http import ApiError, Input, database_session
from services.catalog.models import CatalogRevision, Category, Product

router = APIRouter(prefix="/v1")
PageSize = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=64)]


class ProductView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    category_name: str
    name: str
    description: str
    image_url: str | None
    price_cents: int
    available: bool


class ProductPage(BaseModel):
    revision: int
    items: list[ProductView]
    next_cursor: str | None


class ProductUpdate(Input):
    expected_revision: int = Field(strict=True, gt=0, le=2147483647)
    price_cents: int | None = Field(default=None, strict=True, gt=0, le=2147483647)
    available: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def require_changes(self):
        changes = self.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if not changes or None in changes.values():
            raise ValueError("Informe preço ou disponibilidade válidos.")
        return self


class UpdatedProduct(BaseModel):
    revision: int
    product: ProductView


def require_admin(request: Request):
    authorize_staff(request, "admin")


def require_admin_mutation(request: Request):
    authorize_staff(request, "admin", require_csrf=True)


def read_revision(db, *, lock=False):
    query = select(CatalogRevision.revision).where(CatalogRevision.id == 1)
    revision = db.scalar(query.with_for_update(read=True) if lock else query)
    if revision is None:
        raise ApiError(503, "catalog_unavailable", "Catálogo ainda não provisionado.")
    return revision


def products_query():
    return select(*Product.__table__.c, Category.name.label("category_name")).join(Category)


def decode_cursor(cursor: str) -> UUID:
    try:
        decoded = UUID(bytes=base64.b64decode(cursor, altchars=b"-_", validate=True))
        if encode_cursor(decoded) == cursor:
            return decoded
    except (binascii.Error, ValueError):
        pass
    raise ApiError(422, "invalid_cursor", "Cursor de catálogo inválido.")


def encode_cursor(product_id: UUID) -> str:
    return base64.urlsafe_b64encode(product_id.bytes).decode()


def read_page(db, query, cursor, limit):
    if cursor is not None:
        query = query.where(Product.id > decode_cursor(cursor))

    # Hold a shared lock so the revision and products describe the same version.
    revision = read_revision(db, lock=True)
    rows = db.execute(query.order_by(Product.id).limit(limit + 1)).all()
    return ProductPage(
        revision=revision,
        items=[ProductView.model_validate(row) for row in rows[:limit]],
        next_cursor=encode_cursor(rows[limit - 1].id) if len(rows) > limit else None,
    )


@router.get("/products", response_model=ProductPage)
def public_products(
    q: Annotated[str, Query(max_length=120)] = "",
    category_id: UUID | None = None,
    cursor: Cursor = None,
    limit: PageSize = 20,
    db=Depends(database_session),
):
    query = products_query().where(Product.available)
    if q.strip():
        query = query.where(Product.name.icontains(q.strip(), autoescape=True))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)

    return read_page(db, query, cursor, limit)


@router.get("/admin/products", response_model=ProductPage, dependencies=[Depends(require_admin)])
def admin_products(cursor: Cursor = None, limit: PageSize = 20, db=Depends(database_session)):
    return read_page(db, products_query(), cursor, limit)


@router.patch(
    "/products/{product_id}", response_model=UpdatedProduct,
    dependencies=[Depends(require_admin_mutation)],
)
def update_product(product_id: UUID, payload: ProductUpdate, db=Depends(database_session)):
    revision = db.scalar(
        update(CatalogRevision)
        .where(CatalogRevision.id == 1, CatalogRevision.revision == payload.expected_revision)
        .values(revision=CatalogRevision.revision + 1)
        .returning(CatalogRevision.revision)
    )
    if revision is None:
        current = read_revision(db)
        raise ApiError(409, "catalog_changed", "O catálogo foi alterado.", {"revision": current})

    changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
    product = db.scalar(
        update(Product).where(Product.id == product_id).values(**changes).returning(Product.id)
    )
    if product is None:
        raise ApiError(404, "product_not_found", "Produto não encontrado.")

    row = db.execute(products_query().where(Product.id == product_id)).one()
    result = UpdatedProduct(revision=revision, product=ProductView.model_validate(row))
    db.commit()
    return result
