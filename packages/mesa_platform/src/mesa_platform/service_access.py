import os
import secrets

from fastapi import Request

from mesa_platform.http import ApiError


def require_service_key(request: Request, *key_names: str):
    supplied = request.headers.get("X-Mesa-Service-Key", "")
    for name in key_names:
        expected = os.environ.get(name)
        if expected and secrets.compare_digest(expected.encode(), supplied.encode()):
            return

    raise ApiError(403, "forbidden", "Serviço não autorizado.")
