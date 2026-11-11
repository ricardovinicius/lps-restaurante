"""Persist staff identities and revocable sessions."""

import sqlalchemy as sa
from alembic import op

revision = "configuration_0002"
down_revision = "configuration_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "staff_users",
        sa.Column("username", sa.String(80), primary_key=True),
        sa.Column("password_hash", sa.String(161), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'operator')", name="staff_role"),
    )
    op.create_table(
        "staff_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("username", sa.String(80), sa.ForeignKey("staff_users.username", ondelete="CASCADE"), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_staff_sessions_expires_at", "staff_sessions", ["expires_at"])


def downgrade():
    op.drop_table("staff_sessions")
    op.drop_table("staff_users")
