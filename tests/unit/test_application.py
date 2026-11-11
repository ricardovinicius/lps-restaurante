import importlib
import json
import logging
from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from mesa_platform.application import create_app
from mesa_platform.settings import Settings

SERVICES = ["configuration", "catalog", "orders", "deliveries", "tables"]


class DatabaseProbe:
    """Local test double for the readiness probe, not a PostgreSQL integration."""

    def __init__(self):
        self.failed = False
        self.disposed = False

    @contextmanager
    def connect(self):
        if self.failed:
            raise OperationalError("SELECT 1", {}, Exception("secret database details"))
        yield self

    def execute(self, statement):
        assert str(statement) == "SELECT 1"

    def dispose(self):
        self.disposed = True


@pytest.fixture
def database(monkeypatch):
    probe = DatabaseProbe()
    monkeypatch.setattr("mesa_platform.application.create_database_engine", lambda *a, **kw: probe)
    monkeypatch.setattr("mesa_platform.application.schema_is_current", lambda *a: True)
    return probe


@pytest.mark.parametrize("service", SERVICES)
def test_each_service_lifecycle_health_and_openapi(service, database, monkeypatch):
    monkeypatch.setenv("MESA_DATABASE_URL", "postgresql+psycopg://demo:secret@localhost/demo")
    app = importlib.import_module(f"services.{service}.main").app

    with TestClient(app) as client:
        response = client.get("/health/live")
        assert response.json() == {"service": service, "status": "ok"}
        UUID(response.headers["X-Request-ID"])
        assert client.get("/health/ready").status_code == 200
        database.failed = True
        failed = client.get("/health/ready")
        assert failed.status_code == 503
        assert failed.headers["Retry-After"] == "3"
        assert failed.json() == {"service": service, "status": "unavailable"}
        assert "secret" not in failed.text
        assert client.get("/health/live").status_code == 200
        spec = client.get("/openapi.json").json()
        assert set(spec["paths"]) >= {"/health/live", "/health/ready"}

    assert database.disposed


def test_correlation_logs_do_not_include_query_path_or_credentials(database, caplog):
    app = create_app("orders", Settings(database_url="postgresql+psycopg://user:secret@localhost/db"))
    caplog.set_level(logging.INFO, logger="mesa.orders")
    request_id = str(uuid4())

    with TestClient(app) as client:
        response = client.get("/health/live?address=private", headers={
            "X-Request-ID": request_id, "Authorization": "Bearer private-token",
        })
        assert response.headers["X-Request-ID"] == request_id
        invalid = client.get("/private-address", headers={"X-Request-ID": "private-input"})
        assert invalid.status_code == 404
        UUID(invalid.headers["X-Request-ID"])

    records = [json.loads(r.message) for r in caplog.records if r.name == "mesa.orders"]
    assert records[0]["request_id"] == request_id
    assert records[1]["route"] == "unmatched"
    assert "private" not in json.dumps(records)
    assert "secret" not in json.dumps(records)


def test_settings_load_environment_and_hide_database_secret(monkeypatch):
    monkeypatch.setenv("MESA_DATABASE_URL", "postgresql+psycopg://user:private@localhost/db")
    settings = Settings()
    assert "private" not in repr(settings)
    assert settings.database_connect_timeout == 2


def test_readiness_rejects_outdated_schema_while_liveness_stays_up(database, monkeypatch):
    monkeypatch.setattr("mesa_platform.application.schema_is_current", lambda *a: False)
    app = create_app("catalog", Settings(database_url="postgresql+psycopg://user:secret@localhost/db"))

    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 503
        assert client.get("/health/live").status_code == 200
