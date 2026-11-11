"""Initial tables schema. Frozen revision; never imports runtime models."""

from alembic import op
import sqlalchemy as sa

revision = "tables_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('dining_tables',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('available', sa.Boolean(), nullable=False),
    sa.CheckConstraint('number > 0', name='positive_table_number'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )


def downgrade():
    op.drop_table('dining_tables')
