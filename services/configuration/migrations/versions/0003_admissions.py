"""Persist admission receipts for coordinated order creation."""

import sqlalchemy as sa
from alembic import op

revision = "configuration_0003"
down_revision = "configuration_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admissions",
        sa.Column("operation_id", sa.Uuid(), primary_key=True),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("configuration_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("configuration_revision > 0", name="positive_admission_revision"),
    )


def downgrade():
    op.drop_table("admissions")
