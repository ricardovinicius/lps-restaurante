from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select

from mesa_platform.access import authorize_staff
from mesa_platform.http import database_session
from services.catalog.models import Product

router = APIRouter(prefix="/v1")


class CatalogSummary(BaseModel):
    available_products: int
    total_products: int


@router.get("/summary", response_model=CatalogSummary)
def summary(request: Request, response: Response, db=Depends(database_session)):
    authorize_staff(request, "admin")
    available, total = db.execute(select(func.count().filter(Product.available), func.count())).one()
    response.headers["Cache-Control"] = "no-store"
    return CatalogSummary(available_products=available, total_products=total)
