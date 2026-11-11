"""Customer ownership, durable checkout recovery and transition replay."""

from alembic import op
import sqlalchemy as sa

revision = "orders_0002"
down_revision = "orders_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("valid_subtotal", "order_items", type_="check")
    op.create_check_constraint("valid_subtotal", "order_items", "subtotal_cents = CAST(quantity AS BIGINT) * unit_price_cents")
    op.create_table("customer_contexts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("token_hash"),
    )
    op.add_column("orders", sa.Column("customer_context_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("orders_customer_context_id_fkey", "orders", "customer_contexts", ["customer_context_id"], ["id"])
    op.create_index("ix_orders_customer_context_id", "orders", ["customer_context_id"])
    op.create_table("checkout_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.String(100), nullable=False),
        sa.Column("customer_context_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("admission", sa.JSON(), nullable=True),
        sa.Column("quote", sa.JSON(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("error_status", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lease_id", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("order_id"),
        sa.UniqueConstraint("principal_id", "idempotency_key", name="unique_checkout_key"),
        sa.ForeignKeyConstraint(["customer_context_id"], ["customer_contexts.id"]),
        sa.CheckConstraint("state IN ('pending', 'succeeded', 'rejected', 'needs_attention')", name="valid_operation_state"),
        sa.CheckConstraint("attempts >= 0", name="valid_attempts"),
    )
    op.create_index("ix_checkout_operations_next_attempt_at", "checkout_operations", ["next_attempt_at"])
    op.add_column("transitions", sa.Column("principal_id", sa.String(100), nullable=True))
    op.add_column("transitions", sa.Column("idempotency_key", sa.Uuid(), nullable=True))
    op.add_column("transitions", sa.Column("payload_hash", sa.String(64), nullable=True))
    op.add_column("transitions", sa.Column("result", sa.JSON(), nullable=True))
    op.create_unique_constraint("unique_transition_key", "transitions", ["principal_id", "idempotency_key"])
    op.create_table("operation_resumes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["operation_id"], ["checkout_operations.id"]),
    )


def downgrade():
    op.drop_table("operation_resumes")
    op.drop_constraint("unique_transition_key", "transitions", type_="unique")
    for column in ("result", "payload_hash", "idempotency_key", "principal_id"):
        op.drop_column("transitions", column)
    op.drop_index("ix_checkout_operations_next_attempt_at", table_name="checkout_operations")
    op.drop_table("checkout_operations")
    op.drop_index("ix_orders_customer_context_id", table_name="orders")
    op.drop_constraint("orders_customer_context_id_fkey", "orders", type_="foreignkey")
    op.drop_column("orders", "customer_context_id")
    op.drop_table("customer_contexts")
    op.drop_constraint("valid_subtotal", "order_items", type_="check")
    op.create_check_constraint("valid_subtotal", "order_items", "subtotal_cents = quantity * unit_price_cents")
