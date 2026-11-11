"""Shared connection mechanics; no business metadata lives here."""

from sqlalchemy import create_engine

from mesa_platform.settings import Settings


def create_database_engine(settings: Settings):
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=2,
        connect_args={
            "connect_timeout": settings.database_connect_timeout,
            "options": "-c statement_timeout=5000 -c lock_timeout=5000",
        },
    )
