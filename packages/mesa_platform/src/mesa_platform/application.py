"""Service lifecycle, health endpoints and sanitized request logging."""

import json
import logging
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from mesa_platform.database import create_database_engine
from mesa_platform.http import install_error_handlers
from mesa_platform.migrations import schema_is_current
from mesa_platform.settings import Settings


class Health(BaseModel):
    service: str
    status: str


def create_app(service: str, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(format="%(message)s", level=settings.log_level)
    logger = logging.getLogger(f"mesa.{service}")
    logger.setLevel(settings.log_level)
    logging.getLogger("alembic.runtime.migration").setLevel(logging.WARNING)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_database_engine(settings)
        app.state.engine = engine

        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title=f"Mesa Fácil — {service}", version="0.1.0", lifespan=lifespan)
    app.state.service = service
    install_error_handlers(app)

    @app.middleware("http")
    async def correlate_request(request: Request, call_next):
        try:
            request_id = str(UUID(request.headers.get("X-Request-ID", "")))
        except ValueError:
            request_id = str(uuid4())

        request.state.request_id = request_id
        started = time.monotonic()
        status = 500

        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Log route templates, never raw paths, queries, bodies or credentials.
            route = request.scope.get("route")
            logger.info(json.dumps({
                "service": service,
                "request_id": request_id,
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status": status,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            }))

    @app.get("/health/live", response_model=Health)
    def live():
        return Health(service=service, status="ok")

    @app.get("/health/ready", response_model=Health, responses={503: {"model": Health}})
    def ready(request: Request, response: Response):
        try:
            with request.app.state.engine.connect() as connection:
                current = schema_is_current(connection, service)
                if not current:
                    response.status_code = 503
                    response.headers["Retry-After"] = "3"
                    return Health(service=service, status="unavailable")
        except SQLAlchemyError:
            response.status_code = 503
            response.headers["Retry-After"] = "3"
            return Health(service=service, status="unavailable")

        return Health(service=service, status="ok")

    return app
