"""Reserve each operator idempotency key once across transitions and dispatches."""

from alembic import op
import sqlalchemy as sa

revision = "orders_0005"
down_revision = "orders_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("action_keys",
        sa.Column("principal_id", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("principal_id", "idempotency_key"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
    )

    # Dispatch transitions reuse their operation key, so the second insert keeps the first row.
    op.execute("""
        INSERT INTO action_keys (principal_id, idempotency_key, order_id, created_at)
        SELECT principal_id, idempotency_key, order_id, created_at FROM dispatch_operations
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO action_keys (principal_id, idempotency_key, order_id, created_at)
        SELECT principal_id, idempotency_key, order_id, created_at FROM transitions
        WHERE principal_id IS NOT NULL AND idempotency_key IS NOT NULL
        ON CONFLICT DO NOTHING
    """)


def downgrade():
    op.drop_table("action_keys")
