from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("status", sa.String(20), nullable=False,
                                      server_default=sa.text("'placed'")))


def downgrade():
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("status")
