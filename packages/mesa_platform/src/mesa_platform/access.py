"""Remote staff authorization for services that do not own sessions."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request as HttpRequest, build_opener

from fastapi import Request

from mesa_platform.http import ApiError

STAFF_COOKIE = "mesa_staff"
CSRF_HEADER = "X-CSRF-Token"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


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
    key = os.environ.get("MESA_CATALOG_ACCESS_KEY")
    if key:
        upstream = HttpRequest(
            f"{url.rstrip('/')}/internal/v1/sessions/verify",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Mesa-Service-Key": key,
                "X-Request-ID": request.state.request_id,
            },
        )
        try:
            with build_opener(NoRedirect).open(upstream, timeout=2) as response:
                return json.load(response)
        except HTTPError as error:
            with error:
                if error.code == 401:
                    raise ApiError(401, "invalid_session", "Entre com sua conta para continuar.") from None
                if error.code == 403:
                    raise ApiError(403, "forbidden", "Operação não autorizada.") from None
        except (URLError, TimeoutError, ValueError):
            pass

    raise ApiError(503, "access_unavailable", "Serviço de acesso indisponível.")
