from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from mesa_platform.access import authorize_staff
from mesa_platform.http import ApiError, database_session
from services.orders.access import allow_read, create_context, creation_principal, recover_context, require_context
from services.orders.models import CheckoutOperation, OperationResume, Order, Transition
from services.orders.orchestration import operation_view, payload_hash, process_operation, register_operation
from services.orders.schemas import Checkout, CustomerContextInput, CustomerRecovery, OperationPage, OperationSummary, OperationView, OrderPage, OrderView, PendingOperation, TransitionInput
from services.orders.views import order_page, order_view, page_rows

router = APIRouter(prefix="/v1")
IdempotencyKey = Annotated[UUID, Header(alias="Idempotency-Key")]
PageSize = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=160)]
NEXT_STATE = {"received": "preparing", "preparing": "ready", "ready": "completed"}


def operator(request: Request):
    return authorize_staff(request, "operator")


def operator_mutation(request: Request):
    return authorize_staff(request, "operator", require_csrf=True)


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
        customer_name=row.payload["customer_name"], origin=row.payload["origin"], attempts=row.attempts,
        created_at=row.created_at, updated_at=row.updated_at, error=row.error,
    ) for row in rows], next_cursor=next_cursor)


@router.post("/orders", status_code=201, response_model=OrderView | PendingOperation)
def create_order(payload: Checkout, request: Request, response: Response, idempotency_key: IdempotencyKey,
    db=Depends(database_session)):
    principal, context_id = creation_principal(request, db, payload.origin)
    operation_id = register_operation(db, principal, context_id, idempotency_key, payload.model_dump(mode="json"))
    process_operation(request.app.state.engine, operation_id, request.state.request_id)
    db.expire_all()
    operation = db.get(CheckoutOperation, operation_id)
    response.headers["Cache-Control"] = "no-store"
    if operation.state == "succeeded":
        return order_view(db, db.get(Order, operation.order_id))
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
    return operation_view(db, operation)


@router.post("/operations/{operation_id}/resume", response_model=OperationView)
def resume_operation(operation_id: UUID, request: Request, db=Depends(database_session)):
    principal = authorize_staff(request, "admin", require_csrf=True)
    operation = db.scalar(select(CheckoutOperation).where(CheckoutOperation.id == operation_id).with_for_update())
    if operation is None:
        raise ApiError(404, "not_found", "Operação não encontrada.")
    if operation.state != "needs_attention":
        raise ApiError(409, "invalid_operation_state", "A operação não está aguardando intervenção.")

    operation.state = "pending"
    operation.attempts = 0
    operation.next_attempt_at = datetime.now(UTC)
    operation.error = None
    operation.error_status = None
    operation.updated_at = datetime.now(UTC)
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
    return order_page(db, query, cursor, limit)


@router.get("/orders/{order_id}", response_model=OrderView)
def get_order(order_id: UUID, request: Request, response: Response, db=Depends(database_session)):
    order = db.get(Order, order_id)
    if order is None:
        raise ApiError(404, "not_found", "Pedido não encontrado.")
    allow_read(request, db, order.customer_context_id)
    response.headers["Cache-Control"] = "no-store"
    return order_view(db, order)


@router.get("/queue", response_model=OrderPage, dependencies=[Depends(operator)])
def queue(response: Response, fulfillment: Literal["pickup"] | None = None, cursor: Cursor = None,
    limit: PageSize = 20, db=Depends(database_session)):
    query = select(Order).where(Order.state != "completed")
    if fulfillment:
        query = query.where(Order.fulfillment == fulfillment)
    response.headers["Cache-Control"] = "no-store"
    return order_page(db, query, cursor, limit)


def previous_transition(db, principal_id, idempotency_key, identity):
    existing = db.scalar(select(Transition).where(
        Transition.principal_id == principal_id,
        Transition.idempotency_key == idempotency_key,
    ))
    if existing is None:
        return None

    if existing.payload_hash != identity:
        raise ApiError(409, "idempotency_conflict", "Esta chave já identifica outra ação.")

    return OrderView.model_validate(existing.result)


@router.post("/orders/{order_id}/transitions", response_model=OrderView)
def transition(order_id: UUID, payload: TransitionInput, idempotency_key: IdempotencyKey,
    response: Response, principal=Depends(operator_mutation), db=Depends(database_session)):
    principal_id = f"operator:{principal['username']}"
    identity = payload_hash({"order_id": str(order_id), **payload.model_dump()})
    existing = previous_transition(db, principal_id, idempotency_key, identity)
    if existing is not None:
        return existing

    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise ApiError(404, "not_found", "Pedido não encontrado.")

    existing = previous_transition(db, principal_id, idempotency_key, identity)
    if existing is not None:
        return existing

    if order.version != payload.expected_version or NEXT_STATE.get(order.state) != payload.target_state:
        raise ApiError(409, "transition_conflict", "O pedido foi alterado ou a transição não é válida.", {
            "state": order.state, "version": order.version,
        })
    previous_state = order.state
    order.state = payload.target_state
    order.version += 1
    order.updated_at = datetime.now(UTC)
    db.flush()
    result = order_view(db, order)
    inserted = db.execute(insert(Transition).values(
        id=uuid4(), order_id=order.id, previous_state=previous_state, target_state=order.state,
        actor_id=uuid5(NAMESPACE_URL, principal_id), principal_id=principal_id,
        idempotency_key=idempotency_key, payload_hash=identity, result=result.model_dump(mode="json"),
    ).on_conflict_do_nothing(constraint="unique_transition_key").returning(Transition.id)).scalar_one_or_none()
    if inserted is None:
        db.rollback()
        raise ApiError(409, "idempotency_conflict", "Esta chave já identifica outra ação.")

    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result
