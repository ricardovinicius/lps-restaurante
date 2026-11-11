import os
from urllib.error import URLError

from mesa_platform.http import ApiError
from mesa_platform.http_client import get_json


def read_features(request, *names):
    base_url = os.environ.get("MESA_CONFIGURATION_URL", "http://configuration:8000")

    try:
        response = get_json(f"{base_url.rstrip('/')}/v1/configuration", request_id=request.state.request_id)
        features = response.body["features"] if response.status == 200 else None
    except (OSError, URLError, ValueError, TypeError, KeyError):
        features = None

    if not isinstance(features, dict) or any(not isinstance(features.get(name), bool) for name in names):
        raise ApiError(503, "configuration_unavailable", "Configuração indisponível no momento.")

    return {name: features[name] for name in names}
