from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from mesa_platform.access import authorize_staff
from mesa_platform.configuration import read_features
from mesa_platform.http import ApiError, database_session
from services.orders.parameters import Cursor, PageSize
from services.orders.projections import order_summary, tv_board
from services.orders.schemas import Fulfillment

router = APIRouter(prefix="/v1")


class TVTicket(BaseModel):
    number: int
    fulfillment: Fulfillment
    table_number: int | None


class TVPage(BaseModel):
    items: list[TVTicket]
    total: int
    next_cursor: str | None


class TVBoard(BaseModel):
    preparing: TVPage
    ready: TVPage


class OrderSummary(BaseModel):
    active_orders: int
    completed_order_value_cents: int


def require_tv(request):
    if not read_features(request, "tv")["tv"]:
        raise ApiError(403, "feature_disabled", "O painel de TV está desabilitado.")


@router.get("/tv", response_model=TVBoard)
def television(request: Request, response: Response, limit: PageSize = 20,
    preparing_cursor: Cursor = None, ready_cursor: Cursor = None, db=Depends(database_session)):
    require_tv(request)
    response.headers["Cache-Control"] = "no-store"
    return tv_board(db, limit, preparing_cursor, ready_cursor)


@router.get("/summary", response_model=OrderSummary)
def summary(request: Request, response: Response, db=Depends(database_session)):
    authorize_staff(request, "admin")
    response.headers["Cache-Control"] = "no-store"
    return order_summary(db)
