"""Run the selected service's immutable Alembic history on its own database."""

import argparse
import importlib
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from mesa_platform.database import create_database_engine
from mesa_platform.settings import Settings

SERVICES = ("configuration", "catalog", "orders", "deliveries", "tables")


def migration_config(service: str) -> Config:
    if service not in SERVICES:
        raise ValueError("Unknown service")

    module = importlib.import_module(f"services.{service}")
    directory = Path(module.__file__).parent / "migrations"
    config = Config()
    config.set_main_option("script_location", str(directory))
    config.attributes["service"] = service
    return config


def check_database_identity(connection, service: str) -> bool:
    row = connection.execute(text("SELECT current_database(), current_user")).one()
    return tuple(row) == (f"mesa_{service}", f"mesa_{service}")


def schema_is_current(connection, service: str) -> bool:
    if not check_database_identity(connection, service):
        return False

    actual = set(MigrationContext.configure(connection).get_current_heads())
    expected = set(ScriptDirectory.from_config(migration_config(service)).get_heads())
    return bool(expected) and actual == expected


def migrate(service: str, settings: Settings) -> None:
    config = migration_config(service)
    engine = create_database_engine(settings)

    try:
        with engine.begin() as connection:
            if not check_database_identity(connection, service):
                raise RuntimeError("Database/user does not belong to this service")

            # Same key per database serializes concurrent startup attempts.
            connection.execute(text("SELECT pg_advisory_xact_lock(63827401)"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("service", choices=SERVICES)
    args = parser.parse_args()
    migrate(args.service, Settings())
    print(f"{args.service}: migrations applied")


if __name__ == "__main__":
    main()
