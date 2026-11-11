"""Tablet credentials. Only an operator binds a browser to a table.

The browser keeps an opaque HttpOnly cookie; Mesas stores only its hash. The public
context id identifies the credential but never authorizes anything by itself.
"""

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from mesa_platform.access import authorize_staff
from mesa_platform.http import ApiError, database_session
from services.tables.features import require_features
from services.tables.models import DiningTable, TableContext
from services.tables.schemas import ContextRequest, ContextView

router = APIRouter(prefix="/v1/table-contexts")
TABLE_COOKIE = "mesa_table"
CONTEXT_AGE = timedelta(hours=8)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def find_context(db, token, *, active=True):
    if not token or len(token) > 128:
        return None

    query = select(TableContext).where(TableContext.token_hash == token_hash(token))
    if active:
        query = query.where(TableContext.revoked_at.is_(None), TableContext.expires_at > datetime.now(UTC))

    return db.scalar(query)


def context_view(context, table):
    return ContextView(
        context_id=context.id, table_id=table.id, table_number=table.number,
        expires_at=context.expires_at, csrf_token=context.csrf_token,
    )


@router.post("", status_code=201, response_model=ContextView)
def provision(payload: ContextRequest, request: Request, response: Response, db=Depends(database_session)):
    principal = authorize_staff(request, "operator", require_csrf=True)
    require_features(request, "tables", "tablet")

    table = db.get(DiningTable, payload.table_id)
    if table is None:
        raise ApiError(404, "table_not_found", "Mesa não encontrada.")
    if not table.available:
        raise ApiError(409, "table_unavailable", "A mesa está indisponível para novos pedidos.")

    # One tablet context per browser: provisioning again replaces the previous one.
    previous = find_context(db, request.cookies.get(TABLE_COOKIE))
    if previous is not None:
        previous.revoked_at = datetime.now(UTC)

    token = secrets.token_urlsafe(32)
    context = TableContext(
        id=uuid4(), table_id=table.id, token_hash=token_hash(token),
        csrf_token=secrets.token_urlsafe(32), created_by=principal["username"],
        expires_at=datetime.now(UTC) + CONTEXT_AGE,
    )
    db.add(context)
    view = context_view(context, table)
    db.commit()

    response.set_cookie(
        TABLE_COOKIE, token, max_age=int(CONTEXT_AGE.total_seconds()), httponly=True,
        samesite="lax", secure=os.environ.get("MESA_SECURE_COOKIES") == "1", path="/api",
    )
    response.headers["Cache-Control"] = "no-store"
    return view


@router.get("/current", response_model=ContextView)
def current(request: Request, response: Response, db=Depends(database_session)):
    context = find_context(db, request.cookies.get(TABLE_COOKIE))
    if context is None:
        raise ApiError(401, "table_context_required", "Este tablet não está vinculado a uma mesa.")

    response.headers["Cache-Control"] = "no-store"
    return context_view(context, db.get(DiningTable, context.table_id))


@router.delete("/current", status_code=204)
def revoke(request: Request, db=Depends(database_session)):
    authorize_staff(request, "operator", require_csrf=True)

    context = find_context(db, request.cookies.get(TABLE_COOKIE), active=False)
    if context is not None and context.revoked_at is None:
        context.revoked_at = datetime.now(UTC)
        db.commit()

    response = Response(status_code=204)
    response.delete_cookie(TABLE_COOKIE, path="/api")
    return response
