import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from mesa_platform.access import CSRF_HEADER, STAFF_COOKIE
from mesa_platform.http import ApiError, Input, database_session
from mesa_platform.service_access import require_service_key
from services.configuration.models import StaffSession, StaffUser
from services.configuration.passwords import verify_password

router = APIRouter()
SESSION_AGE = timedelta(hours=8)
DUMMY_PASSWORD_HASH = "0" * 32 + ":" + "0" * 128
Scope = Literal["admin", "operator"]


class Login(Input):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class Verification(Input):
    token: str = Field(max_length=128)
    required_scope: Literal["admin", "operator", "staff"]
    csrf_token: str | None = Field(default=None, max_length=128)


class Principal(BaseModel):
    username: str
    role: Scope
    expires_at: datetime


class CurrentSession(Principal):
    csrf_token: str


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def lookup(db, token: str | None) -> CurrentSession:
    if token and len(token) <= 128:
        result = db.execute(
            select(StaffSession, StaffUser.role)
            .join(StaffUser)
            .where(StaffSession.token_hash == token_hash(token), StaffSession.expires_at > func.now())
        ).one_or_none()
        if result:
            session, role = result
            return CurrentSession(
                username=session.username, role=role, expires_at=session.expires_at,
                csrf_token=session.csrf_token,
            )

    raise ApiError(401, "invalid_session", "Entre com sua conta para continuar.")


def require_scope(session: CurrentSession, scope: str):
    if scope != "staff" and session.role != scope:
        raise ApiError(403, "forbidden", "Seu perfil não tem permissão para esta operação.")


def require_csrf(session: CurrentSession, token: str | None):
    if not token or not secrets.compare_digest(session.csrf_token.encode(), token.encode()):
        raise ApiError(403, "invalid_csrf", "Validação da sessão inválida.")


def current_session(request: Request, db=Depends(database_session)):
    return lookup(db, request.cookies.get(STAFF_COOKIE))


SessionContext = Annotated[CurrentSession, Depends(current_session)]


def admin_session(session: SessionContext):
    require_scope(session, "admin")
    return session


def admin_mutation(request: Request, session=Depends(admin_session)):
    require_csrf(session, request.headers.get(CSRF_HEADER))


@router.post("/v1/sessions", status_code=201, response_model=Principal)
def login(payload: Login, request: Request, response: Response, db=Depends(database_session)):
    user = db.get(StaffUser, payload.username)
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not valid or not user:
        raise ApiError(401, "invalid_credentials", "Usuário ou senha inválidos.")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + SESSION_AGE
    old_token = request.cookies.get(STAFF_COOKIE)
    db.execute(delete(StaffSession).where(StaffSession.expires_at <= func.now()))
    if old_token:
        db.execute(delete(StaffSession).where(StaffSession.token_hash == token_hash(old_token)))

    db.add(StaffSession(
        token_hash=token_hash(token), username=user.username,
        expires_at=expires_at, csrf_token=secrets.token_urlsafe(32),
    ))
    principal = Principal(username=user.username, role=user.role, expires_at=expires_at)
    db.commit()

    response.set_cookie(
        STAFF_COOKIE, token, max_age=int(SESSION_AGE.total_seconds()), httponly=True,
        samesite="lax", secure=os.environ.get("MESA_SECURE_COOKIES") == "1", path="/api",
    )
    response.headers["Cache-Control"] = "no-store"
    return principal


@router.get("/v1/sessions/current", response_model=CurrentSession)
def get_current_session(session: SessionContext, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return session


@router.delete("/v1/sessions/current", status_code=204)
def logout(request: Request, session: SessionContext, db=Depends(database_session)):
    require_csrf(session, request.headers.get(CSRF_HEADER))
    db.execute(delete(StaffSession).where(
        StaffSession.token_hash == token_hash(request.cookies[STAFF_COOKIE]),
    ))
    db.commit()
    response = Response(status_code=204)
    response.delete_cookie(STAFF_COOKIE, path="/api")
    return response


@router.post("/internal/v1/sessions/verify", response_model=Principal)
def verify(payload: Verification, request: Request, db=Depends(database_session)):
    require_service_key(request, "MESA_CATALOG_ACCESS_KEY", "MESA_ORDERS_ACCESS_KEY")

    session = lookup(db, payload.token)
    require_scope(session, payload.required_scope)
    if payload.csrf_token is not None:
        require_csrf(session, payload.csrf_token)

    return session
