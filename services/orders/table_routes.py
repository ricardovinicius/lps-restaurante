"""“Já pedi”: the permanent history of the tablet's table, from every origin."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select

from mesa_platform.http import database_session
from services.orders.models import Order
from services.orders.parameters import Cursor, PageSize
from services.orders.schemas import TableIdentity, TableOrderPage
from services.orders.table_access import verify_table_context
from services.orders.views import for_tablet, order_page

router = APIRouter(prefix="/v1")


@router.get("/table-orders", response_model=TableOrderPage)
def table_orders(request: Request, response: Response, cursor: Cursor = None, limit: PageSize = 20,
    db=Depends(database_session)):
    # The table comes from the credential only; there is no table_id parameter to choose another.
    table = verify_table_context(request)
    at_table = (Order.fulfillment == "table", Order.table_id == table.table_id)

    page = order_page(db, select(Order).where(*at_table), cursor, limit, newest_first=True)
    for order in page.items:
        for_tablet(order)

    totals = select(func.coalesce(func.sum(Order.total_cents), 0), func.count()).where(*at_table)
    total, count = db.execute(totals).one()
    response.headers["Cache-Control"] = "no-store"

    return TableOrderPage(
        table=TableIdentity(id=table.table_id, number=table.table_number),
        items=page.items, next_cursor=page.next_cursor,
        historical_total_cents=total, order_count=count,
    )
