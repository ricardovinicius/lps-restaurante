"""Explicit demo provisioning, never overwrite existing business data."""

import argparse
import importlib

from sqlalchemy import text

from mesa_platform.database import create_database_engine
from mesa_platform.migrations import SERVICES, schema_is_current
from mesa_platform.settings import Settings


def seed_demo(service: str, settings: Settings) -> None:
    if service not in SERVICES:
        raise ValueError("Unknown service")

    engine = create_database_engine(settings)

    try:
        with engine.begin() as connection:
            if not schema_is_current(connection, service):
                raise RuntimeError("Apply this service's migrations before seeding")

            connection.execute(text("SELECT pg_advisory_xact_lock(63827401)"))
            if service in {"configuration", "catalog", "tables"}:
                importlib.import_module(f"services.{service}.seed").seed(connection)
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("service", choices=SERVICES)
    args = parser.parse_args()
    seed_demo(args.service, Settings())
    print(f"{args.service}: demo data provisioned without overwriting existing rows")


if __name__ == "__main__":
    main()
