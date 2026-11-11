"""Initial deliveries schema. Frozen revision; never imports runtime models."""

from alembic import op
import sqlalchemy as sa

revision = "deliveries_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('deliveries',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('operation_id', sa.Uuid(), nullable=False),
    sa.Column('address', sa.String(length=500), nullable=False),
    sa.Column('fee_cents', sa.Integer(), nullable=False),
    sa.Column('transition_id', sa.Uuid(), nullable=True),
    sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(transition_id IS NULL) = (dispatched_at IS NULL)', name='dispatch_fields_together'),
    sa.CheckConstraint('fee_cents = 500', name='fixed_delivery_fee'),
    sa.CheckConstraint('length(trim(address)) > 0', name='address_required'),
    sa.PrimaryKeyConstraint('order_id'),
    sa.UniqueConstraint('operation_id'),
    sa.UniqueConstraint('transition_id')
    )


def downgrade():
    op.drop_table('deliveries')
