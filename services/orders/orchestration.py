import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from mesa_platform.http import ApiError
from services.orders.dependencies import obtain_admission, obtain_quote
from services.orders.errors import is_business_rejection
from services.orders.models import CheckoutOperation, Order, OrderItem
from services.orders.schemas import ItemView, OperationView
from services.orders.views import order_view

LEASE_DURATION = timedelta(seconds=30)


class Admission(BaseModel):
    configuration_revision: int = Field(gt=0)


class Quote(BaseModel):
    catalog_revision: int = Field(gt=0)
    items: list[ItemView] = Field(min_length=1)
    total_cents: int = Field(gt=0)


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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


def acquire_operation(engine, operation_id=None):
    now = datetime.now(UTC)
    with Session(engine, expire_on_commit=False) as db:
        query = select(CheckoutOperation).where(
            CheckoutOperation.state == "pending", CheckoutOperation.next_attempt_at <= now,
            or_(CheckoutOperation.lease_expires_at.is_(None), CheckoutOperation.lease_expires_at <= now),
        )
        if operation_id is not None:
            query = query.where(CheckoutOperation.id == operation_id)

        operation = db.scalar(query.order_by(CheckoutOperation.next_attempt_at, CheckoutOperation.id)
            .with_for_update(skip_locked=True).limit(1))
        if operation is None:
            return None

        if operation.attempts >= 10:
            operation.state = "needs_attention"
            operation.lease_id = None
            operation.lease_expires_at = None
            operation.error = operation.error or {
                "code": "recovery_interrupted", "message": "A operação precisa de retomada pelo administrador.", "details": None,
            }
            operation.error_status = operation.error_status or 503
            operation.updated_at = now
            db.commit()
            return None

        operation.lease_id = uuid4()
        operation.lease_expires_at = now + LEASE_DURATION
        operation.attempts += 1
        operation.updated_at = now
        db.commit()
        return operation


def leased_operation(db, operation):
    return db.scalar(select(CheckoutOperation).where(
        CheckoutOperation.id == operation.id, CheckoutOperation.lease_id == operation.lease_id,
        CheckoutOperation.state == "pending",
    ).with_for_update())


def save_progress(engine, operation, field, result):
    with Session(engine) as db:
        row = leased_operation(db, operation)
        if row is None:
            return False

        setattr(row, field, result)
        row.updated_at = datetime.now(UTC)
        db.commit()
        setattr(operation, field, result)
        return True


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


def finish_operation(engine, operation):
    with Session(engine) as db:
        row = leased_operation(db, operation)
        if row is None:
            return

        quote = row.quote
        payload = row.payload
        db.add(Order(
            id=row.order_id, origin=payload["origin"], fulfillment=payload["fulfillment"],
            customer_name=payload["customer_name"], customer_context_id=row.customer_context_id,
            state="received", version=1, configuration_revision=row.admission["configuration_revision"],
            catalog_revision=quote["catalog_revision"], fee_cents=0, total_cents=quote["total_cents"],
        ))
        db.flush()
        db.add_all(OrderItem(
            order_id=row.order_id, product_id=UUID(item["product_id"]), name=item["name"],
            unit_price_cents=item["unit_price_cents"], quantity=item["quantity"], subtotal_cents=item["subtotal_cents"],
        ) for item in quote["items"])
        row.state = "succeeded"
        row.error = None
        row.error_status = None
        row.lease_id = None
        row.lease_expires_at = None
        row.updated_at = datetime.now(UTC)
        db.commit()


def record_failure(engine, operation, error):
    with Session(engine) as db:
        row = leased_operation(db, operation)
        if row is None:
            return

        row.error = {"code": error.code, "message": error.message, "details": error.details}
        row.error_status = error.status
        row.lease_id = None
        row.lease_expires_at = None
        row.updated_at = datetime.now(UTC)
        if is_business_rejection(error):
            row.state = "rejected"
        elif row.attempts >= 10:
            row.state = "needs_attention"
        else:
            row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=min(3 * 2 ** (row.attempts - 1), 60))
        db.commit()


def process_operation(engine, operation_id=None, request_id=None):
    operation = acquire_operation(engine, operation_id)
    if operation is None:
        return False

    request_id = request_id or str(uuid4())
    try:
        if operation.admission is None:
            try:
                result = Admission.model_validate(obtain_admission(operation, request_id))
                if result.configuration_revision != operation.payload["configuration_revision"]:
                    raise ValueError
            except (ValidationError, ValueError):
                raise ApiError(503, "dependency_unavailable", "Não foi possível validar a admissão. A operação será retomada.") from None
            if not save_progress(engine, operation, "admission", result.model_dump()):
                return True

        if operation.quote is None:
            quote = validate_quote(operation, obtain_quote(operation, request_id))
            if not save_progress(engine, operation, "quote", quote):
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
