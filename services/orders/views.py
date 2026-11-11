import base64
import binascii
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, tuple_

from mesa_platform.http import ApiError
from services.orders.models import Order, OrderItem
from services.orders.schemas import ItemView, OrderPage, OrderView


def order_view(db, row, items=None):
    if items is None:
        items = db.scalars(select(OrderItem).where(OrderItem.order_id == row.id).order_by(OrderItem.product_id))
    return OrderView(
        id=row.id, number=row.number, origin=row.origin, fulfillment=row.fulfillment,
        customer_name=row.customer_name, state=row.state, version=row.version,
        configuration_revision=row.configuration_revision, catalog_revision=row.catalog_revision,
        items=[ItemView.model_validate(item) for item in items], fee_cents=row.fee_cents,
        total_cents=row.total_cents, created_at=row.created_at, updated_at=row.updated_at,
    )


def decode_cursor(cursor):
    try:
        value = base64.b64decode(cursor, altchars=b"-_", validate=True).decode()
        timestamp, identifier = value.split("|", 1)
        timestamp = datetime.fromisoformat(timestamp)
        if timestamp.tzinfo is None:
            raise ValueError
        return timestamp, UUID(identifier)
    except (ValueError, UnicodeError, binascii.Error):
        raise ApiError(422, "invalid_cursor", "Cursor de paginação inválido.") from None


def page_rows(db, query, model, cursor, limit):
    if cursor:
        timestamp, identifier = decode_cursor(cursor)
        query = query.where(tuple_(model.created_at, model.id) > tuple_(timestamp, identifier))

    rows = db.scalars(query.order_by(model.created_at, model.id).limit(limit + 1)).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = base64.urlsafe_b64encode(f"{last.created_at.isoformat()}|{last.id}".encode()).decode()

    return rows[:limit], next_cursor


def order_page(db, query, cursor, limit):
    rows, next_cursor = page_rows(db, query, Order, cursor, limit)
    grouped = {row.id: [] for row in rows}
    if rows:
        items = db.scalars(select(OrderItem).where(OrderItem.order_id.in_(grouped)).order_by(OrderItem.product_id))
        for item in items:
            grouped[item.order_id].append(item)
    return OrderPage(items=[order_view(db, row, grouped[row.id]) for row in rows], next_cursor=next_cursor)
