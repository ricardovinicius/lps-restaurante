"""Lease, retry and attention rules shared by checkout and dispatch operations."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

LEASE_DURATION = timedelta(seconds=30)
MAX_ATTEMPTS = 10
MAX_BACKOFF_SECONDS = 60
EXHAUSTED_ERROR = {
    "code": "recovery_interrupted",
    "message": "A operação precisa de retomada pelo administrador.",
    "details": None,
}


def release(row):
    row.lease_id = None
    row.lease_expires_at = None
    row.updated_at = datetime.now(UTC)


def acquire(engine, model, operation_id=None):
    """Lease one due pending operation, or the given one, for this process."""
    now = datetime.now(UTC)

    with Session(engine, expire_on_commit=False) as db:
        query = select(model).where(
            model.state == "pending",
            model.next_attempt_at <= now,
            or_(model.lease_expires_at.is_(None), model.lease_expires_at <= now),
        )
        if operation_id is not None:
            query = query.where(model.id == operation_id)

        operation = db.scalar(
            query.order_by(model.next_attempt_at, model.id).with_for_update(skip_locked=True).limit(1)
        )
        if operation is None:
            return None

        if operation.attempts >= MAX_ATTEMPTS:
            operation.state = "needs_attention"
            operation.error = operation.error or EXHAUSTED_ERROR
            operation.error_status = operation.error_status or 503
            release(operation)
            db.commit()
            return None

        operation.lease_id = uuid4()
        operation.lease_expires_at = now + LEASE_DURATION
        operation.attempts += 1
        operation.updated_at = now
        db.commit()
        return operation


def leased(db, model, operation):
    """Lock the row only while this process still owns the lease."""
    return db.scalar(select(model).where(
        model.id == operation.id,
        model.lease_id == operation.lease_id,
        model.state == "pending",
    ).with_for_update())


def record_error(row, error, *, rejected=False):
    row.error = {"code": error.code, "message": error.message, "details": error.details}
    row.error_status = error.status
    release(row)

    if rejected:
        row.state = "rejected"
    elif row.attempts >= MAX_ATTEMPTS:
        row.state = "needs_attention"
    else:
        delay = min(3 * 2 ** (row.attempts - 1), MAX_BACKOFF_SECONDS)
        row.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)


def require_attention(row, code, message):
    row.state = "needs_attention"
    row.error = {"code": code, "message": message, "details": None}
    row.error_status = 409
    release(row)


def resume(row):
    row.state = "pending"
    row.attempts = 0
    row.next_attempt_at = datetime.now(UTC)
    row.error = None
    row.error_status = None
    row.updated_at = datetime.now(UTC)
