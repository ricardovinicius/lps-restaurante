"""Remote staff authorization for services that do not own sessions."""

import os
from urllib.error import URLError

from fastapi import Request

from mesa_platform.http import ApiError
from mesa_platform.http_client import post_json

STAFF_COOKIE = "mesa_staff"
CSRF_HEADER = "X-CSRF-Token"


def authorize_staff(request: Request, scope: str, *, require_csrf: bool = False):
    token = request.cookies.get(STAFF_COOKIE)
    if not token or len(token) > 128:
        raise ApiError(401, "invalid_session", "Entre com sua conta para continuar.")

    payload = {"token": token, "required_scope": scope}
    if require_csrf:
        csrf_token = request.headers.get(CSRF_HEADER)
        if not csrf_token or len(csrf_token) > 128:
            raise ApiError(403, "invalid_csrf", "Validação da sessão inválida.")

        payload["csrf_token"] = csrf_token

    url = os.environ.get("MESA_CONFIGURATION_URL", "http://configuration:8000")
    service = request.app.state.service.upper()
    key = os.environ.get(f"MESA_{service}_ACCESS_KEY")
    if key:
        try:
            response = post_json(
                f"{url.rstrip('/')}/internal/v1/sessions/verify",
                payload,
                service_key=key,
                request_id=request.state.request_id,
            )
        except (OSError, URLError, ValueError):
            pass
        else:
            if response.status == 200:
                return response.body
            if response.status == 401:
                raise ApiError(401, "invalid_session", "Entre com sua conta para continuar.")
            if response.status == 403:
                raise ApiError(403, "forbidden", "Operação não autorizada.")

    raise ApiError(503, "access_unavailable", "Serviço de acesso indisponível.")
