from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from mesa_platform.access import authorize_staff
from mesa_platform.http import ApiError, database_session
from services.orders.access import allow_read, create_context, creation_principal, recover_context, require_context
from services.orders.delivery_details import with_delivery_details
from services.orders.leases import resume
from services.orders.models import CheckoutOperation, OperationResume, Order
from services.orders.orchestration import operation_view, process_operation, register_operation
from services.orders.parameters import Cursor, IdempotencyKey, PageSize, operator
from services.orders.schemas import (
    Checkout, CustomerContextInput, CustomerRecovery, Fulfillment, OperationPage, OperationSummary,
    OperationView, OrderPage, OrderView, PendingOperation,
)
from services.orders.views import order_page, order_view, page_rows

router = APIRouter(prefix="/v1")


def detailed_page(db, page, request):
    with_delivery_details(db, page.items, request.state.request_id)
    return page


def detailed_order(db, order, request):
    return with_delivery_details(db, [order_view(db, order)], request.state.request_id)[0]


def detailed_operation(db, operation, request):
    view = operation_view(db, operation)
    if view.order is not None:
        with_delivery_details(db, [view.order], request.state.request_id)
    return view


@router.post("/customer-contexts", status_code=201)
def customer_context(request: Request, response: Response, payload: CustomerContextInput | None = None,
    db=Depends(database_session)):
    return create_context(request, response, db,
        payload.recovery_token if payload else None, payload.new_context if payload else False)


@router.post("/customer-contexts/recover")
def recover_customer_context(payload: CustomerRecovery, request: Request, response: Response, db=Depends(database_session)):
    return recover_context(payload, request, response, db)


@router.get("/operations", response_model=OperationPage)
def operations(request: Request, response: Response,
    state: Literal["pending", "needs_attention", "rejected", "succeeded"] | None = "needs_attention",
    reference: UUID | None = None, cursor: Cursor = None, limit: PageSize = 20,
    db=Depends(database_session)):
    authorize_staff(request, "staff")
    query = select(CheckoutOperation)
    if reference:
        query = query.where((CheckoutOperation.id == reference) | (CheckoutOperation.idempotency_key == reference))
    elif state:
        query = query.where(CheckoutOperation.state == state)
    rows, next_cursor = page_rows(db, query, CheckoutOperation, cursor, limit)
    response.headers["Cache-Control"] = "no-store"
    return OperationPage(items=[OperationSummary(
        operation_id=row.id, idempotency_key=row.idempotency_key, state=row.state,
        customer_name=row.payload["customer_name"], origin=row.payload["origin"],
        fulfillment=row.payload["fulfillment"], attempts=row.attempts,
        created_at=row.created_at, updated_at=row.updated_at, error=row.error,
    ) for row in rows], next_cursor=next_cursor)


@router.post("/orders", status_code=201, response_model=OrderView | PendingOperation)
def create_order(payload: Checkout, request: Request, response: Response, idempotency_key: IdempotencyKey,
    db=Depends(database_session)):
    principal, context_id = creation_principal(request, db, payload.origin)
    body = payload.model_dump(mode="json", exclude_none=True)
    operation_id = register_operation(db, principal, context_id, idempotency_key, body)
    process_operation(request.app.state.engine, operation_id, request.state.request_id)
    db.expire_all()
    operation = db.get(CheckoutOperation, operation_id)
    response.headers["Cache-Control"] = "no-store"
    if operation.state == "succeeded":
        return detailed_order(db, db.get(Order, operation.order_id), request)
    if operation.state == "rejected":
        error = operation.error
        raise ApiError(operation.error_status, error["code"], error["message"], error.get("details"))

    response.status_code = 202
    return PendingOperation(operation_id=operation.id, state=operation.state,
        status_url=f"/api/orders/v1/operations/{operation.id}")


@router.get("/operations/{operation_id}", response_model=OperationView)
def get_operation(operation_id: UUID, request: Request, response: Response, db=Depends(database_session)):
    operation = db.get(CheckoutOperation, operation_id)
    if operation is None:
        raise ApiError(404, "not_found", "Operação não encontrada.")
    allow_read(request, db, operation.customer_context_id, staff_scope="staff")
    response.headers["Cache-Control"] = "no-store"
    return detailed_operation(db, operation, request)


@router.post("/operations/{operation_id}/resume", response_model=OperationView)
def resume_operation(operation_id: UUID, request: Request, db=Depends(database_session)):
    principal = authorize_staff(request, "admin", require_csrf=True)
    operation = db.scalar(select(CheckoutOperation).where(CheckoutOperation.id == operation_id).with_for_update())
    if operation is None:
        raise ApiError(404, "not_found", "Operação não encontrada.")
    if operation.state != "needs_attention":
        raise ApiError(409, "invalid_operation_state", "A operação não está aguardando intervenção.")

    resume(operation)
    db.add(OperationResume(id=uuid4(), operation_id=operation.id, actor=principal["username"]))
    db.commit()
    return operation_view(db, operation)


@router.get("/my-orders", response_model=OrderPage)
def my_orders(request: Request, response: Response, cursor: Cursor = None, limit: PageSize = 20,
    status: Literal["active", "completed"] | None = None,
    db=Depends(database_session)):
    context = require_context(request, db)
    response.headers["Cache-Control"] = "no-store"
    query = select(Order).where(Order.customer_context_id == context.id)
    if status == "active":
        query = query.where(Order.state != "completed")
    elif status == "completed":
        query = query.where(Order.state == "completed")
    return detailed_page(db, order_page(db, query, cursor, limit), request)


@router.get("/orders/{order_id}", response_model=OrderView)
def get_order(order_id: UUID, request: Request, response: Response, db=Depends(database_session)):
    order = db.get(Order, order_id)
    if order is None:
        raise ApiError(404, "not_found", "Pedido não encontrado.")
    allow_read(request, db, order.customer_context_id)
    response.headers["Cache-Control"] = "no-store"
    return detailed_order(db, order, request)


@router.get("/queue", response_model=OrderPage, dependencies=[Depends(operator)])
def queue(request: Request, response: Response, fulfillment: Fulfillment | None = None, cursor: Cursor = None,
    limit: PageSize = 20, db=Depends(database_session)):
    query = select(Order).where(Order.state != "completed")
    if fulfillment:
        query = query.where(Order.fulfillment == fulfillment)
    response.headers["Cache-Control"] = "no-store"
    return detailed_page(db, order_page(db, query, cursor, limit), request)
