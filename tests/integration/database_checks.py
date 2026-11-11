"""Executed inside each service container against its real PostgreSQL database.

All mutations are rolled back. This checks persistence mechanics, not API flows.
"""

import importlib
import os

from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from mesa_platform.database import create_database_engine
from mesa_platform.migrations import SERVICES, schema_is_current, migrate
from mesa_platform.settings import Settings

service = os.environ["MESA_SERVICE"]
settings = Settings()
engine = create_database_engine(settings)
metadata = importlib.import_module(f"services.{service}.models").Base.metadata

with engine.connect() as connection:
    assert schema_is_current(connection, service)
    differences = compare_metadata(MigrationContext.configure(connection), metadata)
    assert differences == [], str(differences)
    for target in SERVICES:
        allowed = connection.scalar(text("SELECT has_database_privilege(current_user, :db, 'CONNECT')"), {"db": f"mesa_{target}"})
        assert allowed == (target == service), f"Unexpected CONNECT to {target}"

# A stale/foreign revision is not a ready schema, even with SELECT 1 working.
with engine.connect() as connection:
    transaction = connection.begin()
    connection.execute(text("UPDATE alembic_version SET version_num='outdated'"))
    assert not schema_is_current(connection, service)
    transaction.rollback()
    assert schema_is_current(connection, service)

# Reject running another service's migrations with this database credential.
wrong_service = next(name for name in SERVICES if name != service)
try:
    migrate(wrong_service, settings)
except RuntimeError as exc:
    assert "does not belong" in str(exc)
else:
    raise AssertionError("Wrong-service migrations were accepted")

# Actually attempt a foreign database connection with this service's credentials.
for target in SERVICES:
    if target == service:
        continue
    foreign = engine.execution_options().url.set(database=f"mesa_{target}")
    other = create_database_engine(Settings(database_url=foreign.render_as_string(hide_password=False)))
    try:
        with other.connect():
            raise AssertionError(f"Cross-service connection allowed: {target}")
    except DBAPIError as exc:
        assert "permission denied for database" in str(exc.orig), "Unexpected connection failure"
    finally:
        other.dispose()

# Enforce a representative invariant at the DB boundary for each service.
invalid = {
    "configuration": "UPDATE configuration SET pickup=false, delivery=false, tables=false WHERE id=1",
    "catalog": "UPDATE products SET price_cents=0",
    "tables": "UPDATE dining_tables SET number=0 WHERE number=1",
    "orders": """INSERT INTO orders (id, origin, fulfillment, customer_name, state, version,
        configuration_revision, catalog_revision, fee_cents, total_cents)
        VALUES ('00000000-0000-0000-0000-000000000001', 'client', 'pickup', 'Teste',
        'dispatched', 1, 1, 1, 0, 100)""",
    "deliveries": """INSERT INTO deliveries (order_id, operation_id, address, fee_cents)
        VALUES ('00000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000001', '', 500)""",
}[service]

with engine.connect() as connection:
    transaction = connection.begin()
    try:
        connection.execute(text(invalid))
    except IntegrityError:
        pass
    else:
        raise AssertionError("Database accepted invalid data")
    finally:
        transaction.rollback()

engine.dispose()
print(f"{service}: migration/model parity, cross-database isolation and constraints passed")

# Seeding preserves operational edits (including a non-default configuration).
if service in {"configuration", "catalog", "tables"}:
    seed = importlib.import_module(f"services.{service}.seed").seed
    changes = {
        "configuration": ("UPDATE configuration SET pickup=false, delivery=true, revision=7", "SELECT revision=7 AND delivery AND NOT pickup FROM configuration"),
        "catalog": ("UPDATE products SET price_cents=8888, available=false", "SELECT bool_and(price_cents=8888 AND NOT available) FROM products"),
        "tables": ("UPDATE dining_tables SET available=false", "SELECT bool_and(NOT available) FROM dining_tables"),
    }
    update, verify = changes[service]
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text(update))
        seed(connection)
        assert connection.scalar(text(verify))
        transaction.rollback()
    engine.dispose()
    print(f"{service}: repeated seeding preserves edits")
