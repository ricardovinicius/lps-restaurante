import os
from urllib.error import URLError

from mesa_platform.http import ApiError
from mesa_platform.http_client import post_json
from services.orders.errors import is_business_rejection


def dependency_error(service, response):
    body = response.body.get("error") if isinstance(response.body, dict) else None
    if not isinstance(body, dict):
        body = {}

    if response.status in (401, 403):
        if (response.status == 403 and body.get("code") == "feature_disabled"
            and service == "configuration" and isinstance(body.get("message"), str)):
            return ApiError(403, "feature_disabled", body["message"], body.get("details"))

        return ApiError(
            503, "dependency_authentication_failed",
            "Falha de acesso a um serviço interno. A operação será retomada.",
        )

    if isinstance(body.get("code"), str) and isinstance(body.get("message"), str):
        failure = ApiError(response.status, body["code"], body["message"], body.get("details"))
        if is_business_rejection(failure):
            return failure

    return ApiError(503, "dependency_unavailable", "Serviço necessário indisponível. A operação será retomada.")


def call_service(service, path, payload, request_id):
    base_url = os.environ.get(f"MESA_{service.upper()}_URL", f"http://{service}:8000")
    key = os.environ.get("MESA_ORDERS_ACCESS_KEY")
    if not key:
        raise ApiError(503, "dependency_unavailable", "Serviço necessário indisponível.")

    try:
        response = post_json(
            f"{base_url.rstrip('/')}{path}", payload,
            service_key=key, request_id=request_id,
        )
    except (OSError, URLError, ValueError):
        raise ApiError(
            503, "dependency_unavailable",
            "Serviço necessário indisponível. A operação será retomada.",
        ) from None

    if 200 <= response.status < 300:
        return response.body

    raise dependency_error(service, response)


def obtain_admission(operation, request_id):
    payload = operation.payload
    return call_service("configuration", f"/internal/v1/admissions/{operation.id}", {
        "principal": operation.principal_id, "revision": payload["configuration_revision"],
        "origin": payload["origin"], "fulfillment": payload["fulfillment"],
    }, request_id)


def obtain_quote(operation, request_id):
    return call_service("catalog", f"/internal/v1/quotes/{operation.id}", {
        "expected_revision": operation.payload["catalog_revision"], "items": operation.payload["items"],
    }, request_id)
