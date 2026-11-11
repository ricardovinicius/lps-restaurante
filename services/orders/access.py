import hashlib
import os
import secrets
from uuid import uuid4

from fastapi import Request, Response
from sqlalchemy import select

from mesa_platform.access import STAFF_COOKIE, authorize_staff
from mesa_platform.http import ApiError
from services.orders.models import CustomerContext

CUSTOMER_COOKIE = "mesa_customer"


def find_context(request: Request, db):
    token = request.cookies.get(CUSTOMER_COOKIE)
    if not token or len(token) > 128:
        return None

    digest = hashlib.sha256(token.encode()).hexdigest()
    return db.scalar(select(CustomerContext).where(CustomerContext.token_hash == digest))


def require_context(request: Request, db):
    context = find_context(request, db)
    if context is None:
        raise ApiError(401, "invalid_customer_context", "Inicie seu atendimento para continuar.")
    return context


def set_context_cookie(response, token):
    response.set_cookie(
        CUSTOMER_COOKIE, token, max_age=31536000, httponly=True,
        samesite="lax", secure=os.environ.get("MESA_SECURE_COOKIES") == "1", path="/api",
    )


def create_context(request: Request, response: Response, db, recovery_token=None, new_context=False):
    context = None if new_context else find_context(request, db)
    if context is None:
        token = secrets.token_urlsafe(32)
        context = CustomerContext(id=uuid4(), token_hash=hashlib.sha256(token.encode()).hexdigest())
        db.add(context)
        set_context_cookie(response, token)
    if recovery_token:
        context.recovery_token_hash = hashlib.sha256(recovery_token.encode()).hexdigest()
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"context_id": context.id}


def recover_context(payload, request, response, db):
    context = db.scalar(select(CustomerContext).where(CustomerContext.id == payload.context_id).with_for_update())
    digest = hashlib.sha256(payload.recovery_token.encode()).hexdigest()
    if context is None or not context.recovery_token_hash or not secrets.compare_digest(context.recovery_token_hash, digest):
        raise ApiError(401, "customer_recovery_required", "Não foi possível recuperar a identificação. Verifique o envio com o atendimento.")
    current = find_context(request, db)
    if current and current.id == context.id:
        response.headers["Cache-Control"] = "no-store"
        return {"context_id": context.id}
    token = secrets.token_urlsafe(32)
    context.token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.commit()
    set_context_cookie(response, token)
    response.headers["Cache-Control"] = "no-store"
    return {"context_id": context.id}


def creation_principal(request: Request, db, origin):
    if origin == "counter":
        principal = authorize_staff(request, "operator", require_csrf=True)
        return f"operator:{principal['username']}", None

    context = require_context(request, db)
    expected = request.headers.get("X-Customer-Context")
    if expected and expected != str(context.id):
        raise ApiError(401, "invalid_customer_context", "Recupere a identificação original antes de repetir o envio.")
    return f"customer:{context.id}", context.id


def allow_read(request: Request, db, customer_context_id, staff_scope="operator"):
    context = find_context(request, db)
    if context is not None and context.id == customer_context_id:
        return
    if request.cookies.get(STAFF_COOKIE):
        authorize_staff(request, staff_scope)
        return
    raise ApiError(404, "not_found", "Pedido ou operação não encontrado.")
