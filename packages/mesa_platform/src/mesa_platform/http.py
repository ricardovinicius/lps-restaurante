"""Shared HTTP errors and database session lifecycle."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy.orm import Session


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def install_error_handlers(app):
    @app.exception_handler(ApiError)
    async def business_error(request, error):
        return JSONResponse(
            {
                "error": {"code": error.code, "message": error.message, "details": error.details},
                "request_id": request.state.request_id,
            },
            status_code=error.status,
            headers={"Retry-After": "3"} if error.status == 503 else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        details = [
            {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
            for item in error.errors()
        ]
        return await business_error(
            request, ApiError(422, "invalid_input", "Confira os dados enviados.", details),
        )

    @app.exception_handler(OperationalError)
    @app.exception_handler(TimeoutError)
    async def database_unavailable(request, error):
        return await business_error(
            request, ApiError(503, "database_unavailable", "Banco de dados indisponível."),
        )


def database_session(request: Request):
    with Session(request.app.state.engine) as session:
        yield session
