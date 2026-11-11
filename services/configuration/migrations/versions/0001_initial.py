"""Initial configuration schema. Frozen revision; never imports runtime models."""

from alembic import op
import sqlalchemy as sa

revision = "configuration_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('configuration',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('pickup', sa.Boolean(), nullable=False),
    sa.Column('delivery', sa.Boolean(), nullable=False),
    sa.Column('tables', sa.Boolean(), nullable=False),
    sa.Column('tablet', sa.Boolean(), nullable=False),
    sa.Column('tv', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('NOT tablet OR tables', name='tablet_requires_tables'),
    sa.CheckConstraint('id = 1', name='single_establishment'),
    sa.CheckConstraint('pickup OR delivery OR tables', name='at_least_one_fulfillment'),
    sa.CheckConstraint('revision > 0', name='positive_revision'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('configuration')
