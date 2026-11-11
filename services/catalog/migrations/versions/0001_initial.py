"""Initial catalog schema. Frozen revision; never imports runtime models."""

from alembic import op
import sqlalchemy as sa

revision = "catalog_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('catalog_revision',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.CheckConstraint('id = 1', name='single_catalog'),
    sa.CheckConstraint('revision > 0', name='positive_revision'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('categories',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('products',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('category_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.String(length=1000), nullable=False),
    sa.Column('image_url', sa.String(length=1000), nullable=True),
    sa.Column('price_cents', sa.Integer(), nullable=False),
    sa.Column('available', sa.Boolean(), nullable=False),
    sa.CheckConstraint('price_cents > 0', name='positive_price'),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_products_category_id'), 'products', ['category_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_products_category_id'), table_name='products')
    op.drop_table('products')
    op.drop_table('categories')
    op.drop_table('catalog_revision')
