"""Read the current feature flags from Configuração before new table operations."""

from mesa_platform.configuration import read_features
from mesa_platform.http import ApiError

FEATURE_MESSAGES = {
    "tables": "O atendimento em mesa está desabilitado.",
    "tablet": "A Comanda digital está desabilitada.",
}


def require_features(request, *names):
    features = read_features(request, *names)

    for name in names:
        if features.get(name) is not True:
            raise ApiError(403, "feature_disabled", FEATURE_MESSAGES[name])
