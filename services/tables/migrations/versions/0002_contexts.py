"""Table versions, tablet credentials and idempotent validation receipts."""

from alembic import op
import sqlalchemy as sa

revision = "tables_0002"
down_revision = "tables_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("dining_tables", sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False))
    op.create_check_constraint("positive_table_version", "dining_tables", "version > 0")

    op.create_table("table_validations",
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=False),
        sa.Column("table_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("operation_id"),
        sa.ForeignKeyConstraint(["table_id"], ["dining_tables.id"]),
    )

    op.create_table("table_contexts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        sa.ForeignKeyConstraint(["table_id"], ["dining_tables.id"]),
    )
    op.create_index("ix_table_contexts_table_id", "table_contexts", ["table_id"])


def downgrade():
    op.drop_index("ix_table_contexts_table_id", table_name="table_contexts")
    op.drop_table("table_contexts")
    op.drop_table("table_validations")
    op.drop_constraint("positive_table_version", "dining_tables", type_="check")
    op.drop_column("dining_tables", "version")
