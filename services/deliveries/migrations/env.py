from alembic import context

from services.deliveries.models import Base

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Use python -m mesa_platform.migrations deliveries")

context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)

with context.begin_transaction():
    context.run_migrations()
