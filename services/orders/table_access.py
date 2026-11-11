"""Tablet identity for Pedidos, verified by Mesas on every request.

The tablet credential is never stored here. A failure to verify it is a credential
problem (401/403) or an unavailable dependency (503), never an order rejection.
"""

import os
from urllib.error import URLError
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, ValidationError

from mesa_platform.access import CSRF_HEADER
from mesa_platform.http import ApiError
from mesa_platform.http_client import post_json

TABLE_COOKIE = "mesa_table"
CONTEXT_HEADER = "X-Table-Context"


class TableContext(BaseModel):
    context_id: UUID
    table_id: UUID
    table_number: int


def invalid_context():
    return ApiError(
        401, "invalid_table_context",
        "A identificação da mesa expirou ou foi revogada. Peça ao atendimento para vincular o tablet.",
    )


def request_verification(request, payload):
    base_url = os.environ.get("MESA_TABLES_URL", "http://tables:8000")
    key = os.environ.get("MESA_ORDERS_ACCESS_KEY")
    if not key:
        return None

    try:
        return post_json(
            f"{base_url.rstrip('/')}/internal/v1/table-contexts/verify", payload,
            service_key=key, request_id=request.state.request_id,
        )
    except (OSError, URLError, ValueError):
        return None


def verify_table_context(request: Request, *, require_csrf=False):
    token = request.cookies.get(TABLE_COOKIE)
    if not token or len(token) > 128:
        raise invalid_context()

    payload = {"token": token}
    if require_csrf:
        csrf_token = request.headers.get(CSRF_HEADER)
        if not csrf_token or len(csrf_token) > 128:
            raise ApiError(403, "invalid_csrf", "Validação da mesa inválida.")

        payload["csrf_token"] = csrf_token

    response = request_verification(request, payload)
    if response is not None and response.status == 200:
        try:
            return TableContext.model_validate(response.body)
        except ValidationError:
            pass

    if response is not None and response.status == 401:
        raise invalid_context()

    body = response.body if response is not None and isinstance(response.body, dict) else {}
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    if response is not None and response.status == 403 and error.get("code") == "invalid_csrf":
        raise ApiError(403, "invalid_csrf", "Validação da mesa inválida.")

    # A wrong service key is an integration failure, not a problem with the tablet.
    raise ApiError(503, "tables_unavailable", "Serviço de mesas indisponível. Tente novamente em instantes.")


def tablet_creator(request: Request):
    """Authorize a new round only for the context the pending send was created with."""
    context = verify_table_context(request, require_csrf=True)
    if request.headers.get(CONTEXT_HEADER) != str(context.context_id):
        raise ApiError(
            401, "table_context_changed",
            "Este tablet foi vinculado novamente. Confira o envio anterior com o atendimento.",
        )

    return context


def optional_table_context(request: Request):
    if not request.cookies.get(TABLE_COOKIE):
        return None

    try:
        return verify_table_context(request)
    except ApiError as error:
        if error.status == 401:
            return None
        raise
