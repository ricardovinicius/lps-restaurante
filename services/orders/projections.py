import base64

from sqlalchemy import func, literal, select, true, tuple_, union_all

from services.orders.models import Order
from services.orders.views import decode_cursor


def tv_board(db, limit, preparing_cursor, ready_cursor):
    totals = select(
        func.count().filter(Order.state == "preparing").label("preparing"),
        func.count().filter(Order.state == "ready").label("ready"),
    ).where(Order.state.in_(("preparing", "ready"))).cte("totals")
    queries = []

    for state, cursor in (("preparing", preparing_cursor), ("ready", ready_cursor)):
        query = select(Order.id, Order.created_at, Order.number, Order.fulfillment, Order.table_number).where(
            Order.state == state,
        )
        if cursor:
            timestamp, identifier = decode_cursor(cursor)
            query = query.where(tuple_(Order.created_at, Order.id) > tuple_(timestamp, identifier))

        page = query.order_by(Order.created_at, Order.id).limit(limit + 1).subquery(state + "_page")
        queries.append(select(
            literal(state).label("state"), totals.c[state].label("total"), *page.c,
        ).select_from(totals.outerjoin(page, true())))

    board = {state: {"items": [], "total": 0, "next_cursor": None} for state in ("preparing", "ready")}
    rows = db.execute(union_all(*queries)).mappings().all()

    for state, page in board.items():
        selected = [row for row in rows if row["state"] == state]
        page["total"] = selected[0]["total"]
        tickets = sorted(
            (row for row in selected if row["id"] is not None), key=lambda row: (row["created_at"], row["id"]),
        )
        if len(tickets) > limit:
            last = tickets[limit - 1]
            page["next_cursor"] = base64.urlsafe_b64encode(
                f"{last['created_at'].isoformat()}|{last['id']}".encode(),
            ).decode()

        page["items"] = [{key: row[key] for key in ("number", "fulfillment", "table_number")}
            for row in tickets[:limit]]

    return board


def order_summary(db):
    row = db.execute(select(
        func.count().filter(Order.state != "completed"),
        func.coalesce(func.sum(Order.total_cents).filter(Order.state == "completed"), 0),
    )).one()
    return {"active_orders": row[0], "completed_order_value_cents": int(row[1])}
