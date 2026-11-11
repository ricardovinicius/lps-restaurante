"""Initial orders schema. Frozen revision; never imports runtime models."""

from alembic import op
import sqlalchemy as sa

revision = "orders_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('orders',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('number', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('origin', sa.String(length=10), nullable=False),
    sa.Column('fulfillment', sa.String(length=10), nullable=False),
    sa.Column('customer_name', sa.String(length=120), nullable=True),
    sa.Column('table_id', sa.Uuid(), nullable=True),
    sa.Column('state', sa.String(length=12), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('configuration_revision', sa.Integer(), nullable=False),
    sa.Column('catalog_revision', sa.Integer(), nullable=False),
    sa.Column('fee_cents', sa.Integer(), nullable=False),
    sa.Column('total_cents', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("fulfillment != 'table' OR table_id IS NOT NULL", name='table_required'),
    sa.CheckConstraint("fulfillment IN ('pickup', 'delivery', 'table')", name='valid_fulfillment'),
    sa.CheckConstraint("origin != 'tablet' OR fulfillment = 'table'", name='tablet_requires_table'),
    sa.CheckConstraint("origin = 'tablet' OR length(trim(customer_name)) > 0 AND customer_name IS NOT NULL", name='customer_required'),
    sa.CheckConstraint("origin IN ('client', 'counter', 'tablet')", name='valid_origin'),
    sa.CheckConstraint("state != 'dispatched' OR fulfillment = 'delivery'", name='dispatch_requires_delivery'),
    sa.CheckConstraint("state IN ('received', 'preparing', 'ready', 'dispatched', 'completed')", name='valid_state'),
    sa.CheckConstraint('total_cents >= fee_cents AND fee_cents >= 0', name='valid_totals'),
    sa.CheckConstraint('version > 0 AND configuration_revision > 0 AND catalog_revision > 0', name='positive_revisions'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    op.create_index(op.f('ix_orders_created_at'), 'orders', ['created_at'], unique=False)
    op.create_index(op.f('ix_orders_state'), 'orders', ['state'], unique=False)
    op.create_table('order_items',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('unit_price_cents', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('subtotal_cents', sa.BigInteger(), nullable=False),
    sa.CheckConstraint('quantity BETWEEN 1 AND 99', name='valid_quantity'),
    sa.CheckConstraint('subtotal_cents = quantity * unit_price_cents', name='valid_subtotal'),
    sa.CheckConstraint('unit_price_cents > 0', name='positive_item_price'),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('order_id', 'product_id')
    )
    op.create_table('transitions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('previous_state', sa.String(length=12), nullable=False),
    sa.Column('target_state', sa.String(length=12), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transitions_order_id'), 'transitions', ['order_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_transitions_order_id'), table_name='transitions')
    op.drop_table('transitions')
    op.drop_table('order_items')
    op.drop_index(op.f('ix_orders_state'), table_name='orders')
    op.drop_index(op.f('ix_orders_created_at'), table_name='orders')
    op.drop_table('orders')
