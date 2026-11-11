"""Persist immutable catalog quotes for coordinated order creation."""

import sqlalchemy as sa
from alembic import op

revision = "catalog_0002"
down_revision = "catalog_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quotes",
        sa.Column("operation_id", sa.Uuid(), primary_key=True),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("quotes")
