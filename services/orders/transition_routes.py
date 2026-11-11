"""Operator transitions, including the durable dispatch of delivery orders."""

from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from mesa_platform.access import authorize_staff
from mesa_platform.http import ApiError, database_session
from services.orders.delivery_details import with_delivery_details
from services.orders.dispatch import process_dispatch, register_dispatch
from services.orders.leases import resume
from services.orders.lifecycle import previous_action, record_transition, require_transition, reserve_action_key
from services.orders.models import DispatchOperation, DispatchResume, Order, Transition
from services.orders.orchestration import payload_hash
from services.orders.parameters import Cursor, IdempotencyKey, PageSize, operator_mutation
from services.orders.schemas import (
    DispatchPage, DispatchSummary, OrderView, PendingDispatch, TransitionInput,
)
from services.orders.views import page_rows

router = APIRouter(prefix="/v1")


def pending_dispatch(response, operation):
    response.status_code = 202
    return PendingDispatch(
        operation_id=operation.id, order_id=operation.order_id, state=operation.state,
        status_url=f"/api/orders/v1/orders/{operation.order_id}",
    )


def detailed(db, view, request):
    return with_delivery_details(db, [view], request.state.request_id)[0]


def dispatch_result(db, operation_id, request, response):
    db.expire_all()
    operation = db.get(DispatchOperation, operation_id)
    if operation.state != "succeeded":
        return pending_dispatch(response, operation)

    transition = db.get(Transition, operation.id)
    return detailed(db, OrderView.model_validate(transition.result), request)


@router.post("/orders/{order_id}/transitions", response_model=OrderView | PendingDispatch)
def transition(order_id: UUID, payload: TransitionInput, idempotency_key: IdempotencyKey,
    request: Request, response: Response, principal=Depends(operator_mutation), db=Depends(database_session)):
    response.headers["Cache-Control"] = "no-store"
    principal_id = f"operator:{principal['username']}"
    identity = payload_hash({"order_id": str(order_id), **payload.model_dump()})

    previous = previous_action(db, principal_id, idempotency_key, identity)
    if previous is not None:
        return detailed(db, previous, request) if isinstance(previous, OrderView) else pending_dispatch(response, previous)

    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise ApiError(404, "not_found", "Pedido não encontrado.")

    previous = previous_action(db, principal_id, idempotency_key, identity)
    if previous is not None:
        return detailed(db, previous, request) if isinstance(previous, OrderView) else pending_dispatch(response, previous)

    require_transition(db, order, payload.expected_version, payload.target_state)
    reserve_action_key(db, principal_id, idempotency_key, order.id)

    if payload.target_state == "dispatched":
        operation_id = register_dispatch(db, order, principal_id, idempotency_key, identity)
        process_dispatch(request.app.state.engine, operation_id, request.state.request_id)
        return dispatch_result(db, operation_id, request, response)

    result = record_transition(db, order, payload.target_state, principal_id, idempotency_key, identity)
    db.commit()
    return detailed(db, result, request)


@router.get("/dispatches", response_model=DispatchPage)
def dispatches(request: Request, response: Response,
    state: Literal["pending", "needs_attention", "succeeded"] | None = "needs_attention",
    cursor: Cursor = None, limit: PageSize = 20, db=Depends(database_session)):
    authorize_staff(request, "staff")
    query = select(DispatchOperation)
    if state:
        query = query.where(DispatchOperation.state == state)

    rows, next_cursor = page_rows(db, query, DispatchOperation, cursor, limit)
    orders = {order.id: order for order in db.scalars(
        select(Order).where(Order.id.in_([row.order_id for row in rows]))
    )}
    response.headers["Cache-Control"] = "no-store"

    return DispatchPage(items=[DispatchSummary(
        operation_id=row.id, order_id=row.order_id, order_number=orders[row.order_id].number,
        customer_name=orders[row.order_id].customer_name, state=row.state, attempts=row.attempts,
        created_at=row.created_at, updated_at=row.updated_at, error=row.error,
    ) for row in rows], next_cursor=next_cursor)


@router.post("/dispatches/{operation_id}/resume", response_model=PendingDispatch, status_code=202)
def resume_dispatch(operation_id: UUID, request: Request, response: Response, db=Depends(database_session)):
    principal = authorize_staff(request, "admin", require_csrf=True)
    operation = db.scalar(select(DispatchOperation).where(DispatchOperation.id == operation_id).with_for_update())
    if operation is None:
        raise ApiError(404, "not_found", "Despacho não encontrado.")

    if operation.state != "needs_attention":
        raise ApiError(409, "invalid_operation_state", "O despacho não está aguardando intervenção.")

    resume(operation)
    db.add(DispatchResume(id=uuid4(), operation_id=operation.id, actor=principal["username"]))

    # Built while the row is still locked: after commit the worker may finish it at once.
    accepted = pending_dispatch(response, operation)
    db.commit()
    return accepted
