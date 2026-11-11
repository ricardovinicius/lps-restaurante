"""Public table listing and operator-controlled availability."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select, update

from mesa_platform.access import authorize_staff
from mesa_platform.http import ApiError, database_session
from services.tables.features import require_features
from services.tables.models import DiningTable
from services.tables.schemas import AvailabilityUpdate, TablePage, TableView

router = APIRouter(prefix="/v1/tables")
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("", response_model=TablePage)
def list_tables(request: Request, response: Response, include_unavailable: bool = False,
    cursor: UUID | None = None, limit: PageSize = 20, db=Depends(database_session)):
    if include_unavailable:
        authorize_staff(request, "staff")
    else:
        require_features(request, "tables")

    query = select(DiningTable).order_by(DiningTable.id).limit(limit + 1)
    if not include_unavailable:
        query = query.where(DiningTable.available.is_(True))
    if cursor:
        query = query.where(DiningTable.id > cursor)

    rows = db.scalars(query).all()
    next_cursor = str(rows[limit - 1].id) if len(rows) > limit else None
    response.headers["Cache-Control"] = "no-store"
    return TablePage(items=[TableView.model_validate(row) for row in rows[:limit]], next_cursor=next_cursor)


@router.patch("/{table_id}", response_model=TableView)
def change_availability(table_id: UUID, payload: AvailabilityUpdate, request: Request, db=Depends(database_session)):
    authorize_staff(request, "operator", require_csrf=True)

    # Validations lock the same row, so availability and order admission are ordered.
    row = db.scalar(update(DiningTable).where(
        DiningTable.id == table_id, DiningTable.version == payload.expected_version,
    ).values(available=payload.available, version=DiningTable.version + 1).returning(DiningTable))
    if row is None:
        current = db.get(DiningTable, table_id)
        if current is None:
            raise ApiError(404, "table_not_found", "Mesa não encontrada.")

        raise ApiError(409, "table_changed", "A mesa foi alterada por outra pessoa.", {"version": current.version})

    view = TableView.model_validate(row)
    db.commit()
    return view
