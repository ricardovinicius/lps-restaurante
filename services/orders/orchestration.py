"""Coordinated checkout: admission, quote, delivery address and local order."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from mesa_platform.http import ApiError
from services.orders.dependencies import obtain_admission, obtain_quote, register_delivery
from services.orders.errors import is_business_rejection
from services.orders.leases import acquire, leased, record_error, release
from services.orders.models import CheckoutOperation, Order, OrderItem
from services.orders.schemas import ItemView, OperationView
from services.orders.views import order_view

DELIVERY_FEE_CENTS = 500


class Admission(BaseModel):
    configuration_revision: int = Field(gt=0)


class Quote(BaseModel):
    catalog_revision: int = Field(gt=0)
    items: list[ItemView] = Field(min_length=1)
    total_cents: int = Field(gt=0)


class DeliveryReceipt(BaseModel):
    order_id: UUID
    operation_id: UUID
    fee_cents: int


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def without_address(payload):
    """The address belongs to Entregas; Pedidos keeps it only while it is needed."""
    return {key: value for key, value in payload.items() if key != "address"}


def register_operation(db, principal_id, customer_context_id, key, payload):
    identity = payload_hash({"principal": principal_id, "payload": payload})
    db.execute(insert(CheckoutOperation).values(
        id=uuid4(), order_id=uuid4(), principal_id=principal_id,
        customer_context_id=customer_context_id, idempotency_key=key,
        payload_hash=identity, payload=payload, state="pending", attempts=0,
    ).on_conflict_do_nothing(constraint="unique_checkout_key"))

    operation = db.scalar(select(CheckoutOperation).where(
        CheckoutOperation.principal_id == principal_id, CheckoutOperation.idempotency_key == key,
    ))
    if operation.payload_hash != identity:
        raise ApiError(409, "idempotency_conflict", "Esta chave já identifica outro pedido.")

    operation_id = operation.id
    db.commit()
    return operation_id


def save_progress(engine, operation, field, result, *, forget_address=False):
    with Session(engine) as db:
        row = leased(db, CheckoutOperation, operation)
        if row is None:
            return False

        setattr(row, field, result)
        if forget_address:
            row.payload = without_address(row.payload)
        row.updated_at = datetime.now(UTC)
        db.commit()

    setattr(operation, field, result)
    if forget_address:
        operation.payload = without_address(operation.payload)
    return True


def validate_admission(operation, result):
    try:
        admission = Admission.model_validate(result)
        if admission.configuration_revision != operation.payload["configuration_revision"]:
            raise ValueError

        return admission.model_dump()
    except (ValidationError, ValueError):
        raise ApiError(503, "dependency_unavailable", "Não foi possível validar a admissão. A operação será retomada.") from None


def validate_quote(operation, result):
    try:
        quote = Quote.model_validate(result)
        expected = {item["product_id"]: item for item in operation.payload["items"]}
        if quote.catalog_revision != operation.payload["catalog_revision"] or len(quote.items) != len(expected):
            raise ValueError

        if len({item.product_id for item in quote.items}) != len(quote.items):
            raise ValueError

        for item in quote.items:
            requested = expected[str(item.product_id)]
            if (item.quantity != requested["quantity"] or item.unit_price_cents != requested["expected_unit_price_cents"]
                or item.subtotal_cents != item.quantity * item.unit_price_cents):
                raise ValueError

        if quote.total_cents != sum(item.subtotal_cents for item in quote.items):
            raise ValueError

        return quote.model_dump(mode="json")
    except (ValidationError, ValueError, KeyError):
        raise ApiError(503, "dependency_unavailable", "Não foi possível validar a cotação. A operação será retomada.") from None


def validate_delivery(operation, result):
    try:
        receipt = DeliveryReceipt.model_validate(result)
        if (receipt.order_id != operation.order_id or receipt.operation_id != operation.id
            or receipt.fee_cents != DELIVERY_FEE_CENTS):
            raise ValueError

        return {"fee_cents": receipt.fee_cents}
    except (ValidationError, ValueError):
        raise ApiError(503, "dependency_unavailable", "Não foi possível validar a entrega. A operação será retomada.") from None


def finish_operation(engine, operation):
    with Session(engine) as db:
        row = leased(db, CheckoutOperation, operation)
        if row is None:
            return

        quote = row.quote
        payload = row.payload
        fee_cents = row.delivery["fee_cents"] if payload["fulfillment"] == "delivery" else 0
        db.add(Order(
            id=row.order_id, origin=payload["origin"], fulfillment=payload["fulfillment"],
            customer_name=payload["customer_name"], customer_context_id=row.customer_context_id,
            state="received", version=1, configuration_revision=row.admission["configuration_revision"],
            catalog_revision=quote["catalog_revision"], fee_cents=fee_cents,
            total_cents=quote["total_cents"] + fee_cents,
        ))
        db.flush()

        db.add_all(OrderItem(
            order_id=row.order_id, product_id=UUID(item["product_id"]), name=item["name"],
            unit_price_cents=item["unit_price_cents"], quantity=item["quantity"], subtotal_cents=item["subtotal_cents"],
        ) for item in quote["items"])

        row.state = "succeeded"
        row.error = None
        row.error_status = None
        release(row)
        db.commit()


def record_failure(engine, operation, error):
    with Session(engine) as db:
        row = leased(db, CheckoutOperation, operation)
        if row is None:
            return

        rejected = is_business_rejection(error)
        record_error(row, error, rejected=rejected)
        if rejected:
            row.payload = without_address(row.payload)
        db.commit()


def process_operation(engine, operation_id=None, request_id=None):
    operation = acquire(engine, CheckoutOperation, operation_id)
    if operation is None:
        return False

    request_id = request_id or str(uuid4())

    try:
        if operation.admission is None:
            admission = validate_admission(operation, obtain_admission(operation, request_id))
            if not save_progress(engine, operation, "admission", admission):
                return True

        if operation.quote is None:
            quote = validate_quote(operation, obtain_quote(operation, request_id))
            if not save_progress(engine, operation, "quote", quote):
                return True

        if operation.payload["fulfillment"] == "delivery" and operation.delivery is None:
            receipt = validate_delivery(operation, register_delivery(operation, request_id))
            if not save_progress(engine, operation, "delivery", receipt, forget_address=True):
                return True

        finish_operation(engine, operation)
    except ApiError as error:
        record_failure(engine, operation, error)

    return True


def operation_view(db, operation):
    order = None
    if operation.state == "succeeded":
        order = order_view(db, db.get(Order, operation.order_id))

    return OperationView(operation_id=operation.id, state=operation.state, order=order, error=operation.error)
