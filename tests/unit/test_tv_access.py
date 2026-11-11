from types import SimpleNamespace

import pytest

from mesa_platform.http import ApiError
from mesa_platform.http_client import JsonResponse
from services.orders.read_routes import require_tv
from services.tables.features import require_features


@pytest.mark.parametrize("status,body,expected", [
    (200, {"features": {"tv": True}}, None),
    (200, {"features": {"tv": False}}, (403, "feature_disabled")),
    (200, {"features": {"tv": "false"}}, (503, "configuration_unavailable")),
    (200, {}, (503, "configuration_unavailable")),
    (503, None, (503, "configuration_unavailable")),
])
def test_tv_requires_a_current_valid_feature(monkeypatch, status, body, expected):
    monkeypatch.setattr("mesa_platform.configuration.get_json", lambda *args, **kwargs: JsonResponse(status, body))
    request = SimpleNamespace(state=SimpleNamespace(request_id="test"))
    if expected is None:
        require_tv(request)
    else:
        with pytest.raises(ApiError) as caught:
            require_tv(request)
        assert (caught.value.status, caught.value.code) == expected


@pytest.mark.parametrize("features,status", [
    ({"tables": True, "tablet": True}, None),
    ({"tables": False, "tablet": True}, 403),
    ({"tables": True}, 503),
    ({"tables": "true", "tablet": True}, 503),
])
def test_table_features_use_the_same_strict_read(monkeypatch, features, status):
    monkeypatch.setattr("mesa_platform.configuration.get_json",
        lambda *args, **kwargs: JsonResponse(200, {"features": features}))
    request = SimpleNamespace(state=SimpleNamespace(request_id="test"))
    if status is None:
        require_features(request, "tables", "tablet")
    else:
        with pytest.raises(ApiError) as caught:
            require_features(request, "tables", "tablet")
        assert caught.value.status == status


@pytest.mark.parametrize("failure", [OSError, ValueError])
def test_invalid_feature_responses_remain_unavailable(monkeypatch, failure):
    def unavailable(*args, **kwargs):
        raise failure("internal response details")

    monkeypatch.setattr("mesa_platform.configuration.get_json", unavailable)
    request = SimpleNamespace(state=SimpleNamespace(request_id="test"))
    with pytest.raises(ApiError) as caught:
        require_tv(request)
    assert (caught.value.status, caught.value.code) == (503, "configuration_unavailable")
