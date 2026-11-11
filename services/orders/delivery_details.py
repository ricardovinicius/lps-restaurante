"""Attach live delivery details to order views without copying addresses into Pedidos.

Reads degrade: when Entregas cannot answer, orders are still listed and delivery
details are marked unavailable instead of failing the whole response.
"""

import logging

from sqlalchemy import select

from mesa_platform.http import ApiError
from services.orders.dependencies import lookup_deliveries
from services.orders.models import DispatchOperation
from services.orders.schemas import DeliveryDetails

logger = logging.getLogger("mesa.orders")


def read_deliveries(order_ids, request_id):
    try:
        response = lookup_deliveries(order_ids, request_id)
        return {item["order_id"]: item for item in response["items"]}
    except (ApiError, KeyError, TypeError):
        logger.warning("Delivery details unavailable for %d orders", len(order_ids))
        return None


def details_for(found, order_id):
    if found is None or str(order_id) not in found:
        return DeliveryDetails(available=False)

    item = found[str(order_id)]
    return DeliveryDetails(available=True, address=item["address"], dispatched_at=item["dispatched_at"])


def with_delivery_details(db, views, request_id):
    order_ids = [view.id for view in views if view.fulfillment == "delivery"]
    if not order_ids:
        return views

    dispatches = dict(db.execute(select(DispatchOperation.order_id, DispatchOperation.state).where(
        DispatchOperation.order_id.in_(order_ids),
        DispatchOperation.state != "succeeded",
    )).all())
    found = read_deliveries(order_ids, request_id)

    for view in views:
        if view.fulfillment == "delivery":
            view.delivery = details_for(found, view.id)
            view.dispatch_state = dispatches.get(view.id)

    return views
