"""Public order state machine. Pedidos is the only source of an order's state."""

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from mesa_platform.http import ApiError
from services.orders.models import ActionKey, DispatchOperation, Transition
from services.orders.schemas import OrderView
from services.orders.views import order_view

NEXT_STATE = {
    "pickup": {"received": "preparing", "preparing": "ready", "ready": "completed"},
    "table": {"received": "preparing", "preparing": "ready", "ready": "completed"},
    "delivery": {"received": "preparing", "preparing": "ready", "ready": "dispatched", "dispatched": "completed"},
}

# Enrichment fields are read live from Entregas, never frozen in a replay snapshot.
LIVE_FIELDS = {"delivery", "dispatch_state"}


def idempotency_conflict():
    return ApiError(409, "idempotency_conflict", "Esta chave já identifica outra ação.")


def previous_action(db, principal_id, idempotency_key, identity):
    """Return a finished transition, a dispatch still in progress, or None."""
    transition = db.scalar(select(Transition).where(
        Transition.principal_id == principal_id,
        Transition.idempotency_key == idempotency_key,
    ))
    if transition is not None:
        if transition.payload_hash != identity:
            raise idempotency_conflict()

        return OrderView.model_validate(transition.result)

    dispatch = db.scalar(select(DispatchOperation).where(
        DispatchOperation.principal_id == principal_id,
        DispatchOperation.idempotency_key == idempotency_key,
    ))
    if dispatch is None:
        return None

    if dispatch.payload_hash != identity:
        raise idempotency_conflict()

    # The worker may finish the dispatch between the two lookups above.
    if dispatch.state == "succeeded":
        return OrderView.model_validate(db.get(Transition, dispatch.id).result)

    return dispatch


def reserve_action_key(db, principal_id, idempotency_key, order_id):
    """Claim the key in the caller's transaction; a concurrent claim waits and then conflicts."""
    reserved = db.execute(insert(ActionKey).values(
        principal_id=principal_id,
        idempotency_key=idempotency_key,
        order_id=order_id,
    ).on_conflict_do_nothing().returning(ActionKey.idempotency_key)).scalar_one_or_none()

    if reserved is None:
        db.rollback()
        raise idempotency_conflict()


def require_transition(db, order, expected_version, target_state):
    active_dispatch = db.scalar(select(DispatchOperation.state).where(DispatchOperation.order_id == order.id))
    is_next = NEXT_STATE[order.fulfillment].get(order.state) == target_state
    if order.version != expected_version or not is_next or active_dispatch in ("pending", "needs_attention"):
        raise ApiError(409, "transition_conflict", "O pedido foi alterado ou a transição não é válida.", {
            "state": order.state, "version": order.version,
        })


def record_transition(db, order, target_state, principal_id, idempotency_key, identity, transition_id=None):
    """Apply one edge and its replay snapshot in the caller's transaction."""
    previous_state = order.state
    order.state = target_state
    order.version += 1
    order.updated_at = datetime.now(UTC)
    db.flush()

    result = order_view(db, order)
    inserted = db.execute(insert(Transition).values(
        id=transition_id or uuid4(),
        order_id=order.id,
        previous_state=previous_state,
        target_state=order.state,
        actor_id=uuid5(NAMESPACE_URL, principal_id),
        principal_id=principal_id,
        idempotency_key=idempotency_key,
        payload_hash=identity,
        result=result.model_dump(mode="json", exclude=LIVE_FIELDS),
    ).on_conflict_do_nothing(constraint="unique_transition_key").returning(Transition.id)).scalar_one_or_none()

    if inserted is None:
        db.rollback()
        raise idempotency_conflict()

    return result
