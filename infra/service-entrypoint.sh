#!/bin/sh
set -eu
python -m mesa_platform.migrations "$MESA_SERVICE"
exec uvicorn "services.${MESA_SERVICE}.main:app" --host 0.0.0.0 --port 8000 --no-access-log
