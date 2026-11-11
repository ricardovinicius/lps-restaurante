"""Read the current feature flags from Configuração before new table operations."""

import os
from urllib.error import URLError

from mesa_platform.http import ApiError
from mesa_platform.http_client import get_json

FEATURE_MESSAGES = {
    "tables": "O atendimento em mesa está desabilitado.",
    "tablet": "A Comanda digital está desabilitada.",
}


def require_features(request, *names):
    base_url = os.environ.get("MESA_CONFIGURATION_URL", "http://configuration:8000")

    try:
        response = get_json(f"{base_url.rstrip('/')}/v1/configuration", request_id=request.state.request_id)
        features = response.body["features"] if response.status == 200 else None
    except (OSError, URLError, ValueError, KeyError, TypeError):
        features = None

    if not isinstance(features, dict):
        raise ApiError(503, "configuration_unavailable", "Configuração indisponível no momento.")

    for name in names:
        if features.get(name) is not True:
            raise ApiError(403, "feature_disabled", FEATURE_MESSAGES[name])
