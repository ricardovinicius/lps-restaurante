from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

from mesa_platform.http import ApiError
from services.orders.dependencies import call_service


@pytest.mark.parametrize("service,status,code,expected_status,expected_code", [
    ("configuration", 403, "forbidden", 503, "dependency_authentication_failed"),
    ("catalog", 403, "forbidden", 503, "dependency_authentication_failed"),
    ("configuration", 401, "invalid_session", 503, "dependency_authentication_failed"),
    ("configuration", 403, "feature_disabled", 403, "feature_disabled"),
    ("catalog", 403, "feature_disabled", 503, "dependency_authentication_failed"),
    ("catalog", 409, "catalog_changed", 409, "catalog_changed"),
    ("catalog", 409, "price_changed", 409, "price_changed"),
    ("catalog", 422, "invalid_input", 503, "dependency_unavailable"),
    ("catalog", 409, "unexpected_error", 503, "dependency_unavailable"),
])
def test_dependency_error_classification(monkeypatch, service, status, code, expected_status, expected_code):
    monkeypatch.setenv("MESA_ORDERS_ACCESS_KEY", "test-key")

    class FailingService:
        def open(self, *args, **kwargs):
            body = json.dumps({"error": {"code": code, "message": "Falha demonstrativa"}}).encode()
            raise HTTPError("http://service/internal", status, "Failure", {}, BytesIO(body))

    monkeypatch.setattr("mesa_platform.http_client.build_opener", lambda *args: FailingService())
    with pytest.raises(ApiError) as caught:
        call_service(service, "/internal/v1/test", {}, "request-id")
    assert (caught.value.status, caught.value.code) == (expected_status, expected_code)
