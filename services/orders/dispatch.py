"""Durable "out for delivery" transition coordinated with Entregas.

The order stays `ready` until Entregas confirms the dispatch. The operation id is
also the transition id sent to Entregas, so every retry is an idempotent replay.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from mesa_platform.http import ApiError
from services.orders.dependencies import dispatch_delivery
from services.orders.leases import acquire, leased, record_error, release, require_attention
from services.orders.lifecycle import record_transition
from services.orders.models import DispatchOperation, Order


class DispatchReceipt(BaseModel):
    order_id: UUID
    transition_id: UUID


def register_dispatch(db, order, principal_id, idempotency_key, identity):
    """Persist the intent while the caller holds the order lock."""
    operation = DispatchOperation(
        id=uuid4(), order_id=order.id, principal_id=principal_id,
        idempotency_key=idempotency_key, payload_hash=identity,
        expected_version=order.version, dispatched_at=datetime.now(UTC),
        state="pending", attempts=0,
    )
    db.add(operation)
    db.commit()
    return operation.id


def validate_receipt(operation, result):
    try:
        receipt = DispatchReceipt.model_validate(result)
        if receipt.order_id != operation.order_id or receipt.transition_id != operation.id:
            raise ValueError
    except (ValidationError, ValueError):
        raise ApiError(503, "dependency_unavailable", "Não foi possível validar o despacho. A operação será retomada.") from None


def finish_dispatch(engine, operation):
    with Session(engine) as db:
        row = leased(db, DispatchOperation, operation)
        if row is None:
            return

        order = db.scalar(select(Order).where(Order.id == row.order_id).with_for_update())
        if order.state != "ready" or order.version != row.expected_version:
            require_attention(row, "dispatch_conflict", "O pedido mudou antes da confirmação do despacho.")
            db.commit()
            return

        try:
            record_transition(
                db, order, "dispatched", row.principal_id, row.idempotency_key, row.payload_hash,
                transition_id=row.id,
            )
        except ApiError:
            row = leased(db, DispatchOperation, operation)
            require_attention(row, "dispatch_conflict", "A chave do despacho já identifica outra ação.")
            db.commit()
            return

        row.state = "succeeded"
        row.error = None
        row.error_status = None
        release(row)
        db.commit()


def record_dispatch_failure(engine, operation, error):
    with Session(engine) as db:
        row = leased(db, DispatchOperation, operation)
        if row is None:
            return

        record_error(row, error)
        db.commit()


def process_dispatch(engine, operation_id=None, request_id=None):
    operation = acquire(engine, DispatchOperation, operation_id)
    if operation is None:
        return False

    try:
        validate_receipt(operation, dispatch_delivery(operation, request_id or str(uuid4())))
        finish_dispatch(engine, operation)
    except ApiError as error:
        record_dispatch_failure(engine, operation, error)

    return True
