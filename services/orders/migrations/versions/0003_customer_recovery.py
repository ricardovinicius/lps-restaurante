from alembic import op
import sqlalchemy as sa

revision = "orders_0003"
down_revision = "orders_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customer_contexts", sa.Column("recovery_token_hash", sa.String(64), nullable=True))
    op.execute("""
        UPDATE checkout_operations
        SET state='needs_attention', error_status=503,
            error=json_build_object('code', 'dependency_authentication_failed',
                'message', 'Falha de acesso a um serviço interno. Solicite a retomada ao administrador.', 'details', NULL),
            updated_at=now()
        WHERE state='rejected' AND error_status=403 AND error->>'code'='forbidden'
    """)


def downgrade():
    op.drop_column("customer_contexts", "recovery_token_hash")
