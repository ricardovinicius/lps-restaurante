"""Internal delivery API. Only Pedidos calls it; addresses never leave in errors or logs."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import AwareDatetime, BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from mesa_platform.http import ApiError, Input, database_session
from mesa_platform.service_access import require_service_key
from services.deliveries.models import Delivery

DELIVERY_FEE_CENTS = 500


def require_orders_service(request: Request):
    require_service_key(request, "MESA_ORDERS_ACCESS_KEY")


router = APIRouter(prefix="/internal/v1/deliveries", dependencies=[Depends(require_orders_service)])


class AddressInput(Input):
    operation_id: UUID
    address: str = Field(min_length=1, max_length=500)

    @field_validator("address", mode="before")
    @classmethod
    def trim_address(cls, value):
        return value.strip() if isinstance(value, str) else value


class DispatchInput(Input):
    transition_id: UUID
    dispatched_at: AwareDatetime


class LookupInput(Input):
    order_ids: list[UUID] = Field(min_length=1, max_length=100)


class DeliveryView(BaseModel):
    order_id: UUID
    operation_id: UUID
    address: str
    fee_cents: int
    transition_id: UUID | None
    dispatched_at: datetime | None


class DeliveryPage(BaseModel):
    items: list[DeliveryView]


def delivery_view(row):
    return DeliveryView(
        order_id=row.order_id,
        operation_id=row.operation_id,
        address=row.address,
        fee_cents=row.fee_cents,
        transition_id=row.transition_id,
        dispatched_at=row.dispatched_at,
    )


def idempotency_conflict():
    return ApiError(409, "idempotency_conflict", "A entrega já foi registrada com outros dados.")


@router.put("/{order_id}", status_code=201, response_model=DeliveryView)
def register(order_id: UUID, payload: AddressInput, response: Response, db=Depends(database_session)):
    created = db.scalar(insert(Delivery).values(
        order_id=order_id,
        operation_id=payload.operation_id,
        address=payload.address,
        fee_cents=DELIVERY_FEE_CENTS,
    ).on_conflict_do_nothing().returning(Delivery.order_id))
    db.commit()

    row = db.get(Delivery, order_id)
    if row is None or row.operation_id != payload.operation_id or row.address != payload.address:
        raise idempotency_conflict()

    if created is None:
        response.status_code = 200

    return delivery_view(row)


@router.post("/lookup", response_model=DeliveryPage)
def lookup(payload: LookupInput, db=Depends(database_session)):
    rows = db.scalars(select(Delivery).where(Delivery.order_id.in_(payload.order_ids)))

    return DeliveryPage(items=[delivery_view(row) for row in rows])


@router.put("/{order_id}/dispatch", status_code=201, response_model=DeliveryView)
def dispatch(order_id: UUID, payload: DispatchInput, response: Response, db=Depends(database_session)):
    row = db.scalar(select(Delivery).where(Delivery.order_id == order_id).with_for_update())
    if row is None:
        raise ApiError(404, "delivery_not_found", "Entrega não encontrada.")

    if row.transition_id is None:
        row.transition_id = payload.transition_id
        row.dispatched_at = payload.dispatched_at
        db.commit()
        return delivery_view(row)

    if row.transition_id != payload.transition_id or row.dispatched_at != payload.dispatched_at:
        raise ApiError(409, "idempotency_conflict", "A entrega já foi despachada por outra ação.")

    response.status_code = 200
    return delivery_view(row)
