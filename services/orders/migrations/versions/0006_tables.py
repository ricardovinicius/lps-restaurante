"""Table snapshots on orders, tablet ownership and table receipts during checkout."""

from alembic import op
import sqlalchemy as sa

revision = "orders_0006"
down_revision = "orders_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("table_number", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "table_data_only_for_tables", "orders", "fulfillment = 'table' OR (table_id IS NULL AND table_number IS NULL)",
    )
    op.create_check_constraint("positive_table_number", "orders", "table_number IS NULL OR table_number > 0")
    op.create_index("ix_orders_table_history", "orders", ["table_id", "created_at", "id"])

    op.add_column("checkout_operations", sa.Column("table_context_id", sa.Uuid(), nullable=True))
    op.add_column("checkout_operations", sa.Column("table", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("checkout_operations", "table")
    op.drop_column("checkout_operations", "table_context_id")
    op.drop_index("ix_orders_table_history", table_name="orders")
    op.drop_constraint("positive_table_number", "orders", type_="check")
    op.drop_constraint("table_data_only_for_tables", "orders", type_="check")
    op.drop_column("orders", "table_number")
