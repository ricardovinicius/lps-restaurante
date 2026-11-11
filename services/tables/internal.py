"""Internal API for Pedidos: tablet credential checks and table validation receipts."""

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from mesa_platform.http import ApiError, database_session
from mesa_platform.service_access import require_service_key
from services.tables.contexts import find_context
from services.tables.models import DiningTable, TableValidation
from services.tables.schemas import ContextVerification, ValidationReceipt, ValidationRequest, VerifiedContext


def require_orders_service(request: Request):
    require_service_key(request, "MESA_ORDERS_ACCESS_KEY")


router = APIRouter(prefix="/internal/v1", dependencies=[Depends(require_orders_service)])


@router.post("/table-contexts/verify", response_model=VerifiedContext)
def verify(payload: ContextVerification, db=Depends(database_session)):
    # Features and availability never invalidate a credential: they only block new orders.
    context = find_context(db, payload.token)
    if context is None:
        raise ApiError(401, "invalid_table_context", "A identificação da mesa expirou ou foi revogada.")

    if payload.csrf_token is not None and not secrets.compare_digest(context.csrf_token, payload.csrf_token):
        raise ApiError(403, "invalid_csrf", "Validação da mesa inválida.")

    table = db.get(DiningTable, context.table_id)
    return VerifiedContext(
        context_id=context.id, table_id=table.id, table_number=table.number, expires_at=context.expires_at,
    )


def replay(existing, payload, response):
    if existing.table_id != payload.table_id:
        raise ApiError(409, "idempotency_conflict", "A operação já foi validada para outra mesa.")

    response.status_code = 200
    return ValidationReceipt(
        operation_id=existing.operation_id, table_id=existing.table_id, table_number=existing.table_number,
    )


@router.post("/validations/{operation_id}", status_code=201, response_model=ValidationReceipt)
def validate(operation_id: UUID, payload: ValidationRequest, response: Response, db=Depends(database_session)):
    existing = db.get(TableValidation, operation_id)
    if existing is not None:
        return replay(existing, payload, response)

    table = db.scalar(select(DiningTable).where(DiningTable.id == payload.table_id).with_for_update())
    if table is None:
        raise ApiError(404, "table_not_found", "Mesa não encontrada.")

    # A receipt committed while waiting for the lock wins over the current availability.
    existing = db.get(TableValidation, operation_id)
    if existing is not None:
        return replay(existing, payload, response)

    if not table.available:
        raise ApiError(409, "table_unavailable", "A mesa está indisponível para novos pedidos.")

    created = db.scalar(insert(TableValidation).values(
        operation_id=operation_id, table_id=table.id, table_number=table.number,
    ).on_conflict_do_nothing().returning(TableValidation.operation_id))
    if created is None:
        db.rollback()
        return replay(db.get(TableValidation, operation_id), payload, response)

    receipt = ValidationReceipt(operation_id=operation_id, table_id=table.id, table_number=table.number)
    db.commit()
    return receipt
