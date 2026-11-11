"""Delivery receipts during checkout and durable dispatch operations."""

from alembic import op
import sqlalchemy as sa

revision = "orders_0004"
down_revision = "orders_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("checkout_operations", sa.Column("delivery", sa.JSON(), nullable=True))

    op.create_table("dispatch_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("error_status", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lease_id", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
        sa.UniqueConstraint("principal_id", "idempotency_key", name="unique_dispatch_key"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.CheckConstraint("state IN ('pending', 'succeeded', 'needs_attention')", name="valid_dispatch_state"),
        sa.CheckConstraint("attempts >= 0", name="valid_dispatch_attempts"),
    )
    op.create_index("ix_dispatch_operations_next_attempt_at", "dispatch_operations", ["next_attempt_at"])

    op.create_table("dispatch_resumes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["operation_id"], ["dispatch_operations.id"]),
    )


def downgrade():
    op.drop_table("dispatch_resumes")
    op.drop_index("ix_dispatch_operations_next_attempt_at", table_name="dispatch_operations")
    op.drop_table("dispatch_operations")
    op.drop_column("checkout_operations", "delivery")
