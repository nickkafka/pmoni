"""Remember the periodic facial check: whether it runs, how often, and how it went.

The nightly import leaves whoever is enrolled during the day out of pMoni until the
next night — the porter sees them pass with no name and no face. The check closes
that gap by asking each facial how many people it holds and syncing the ones that
disagree, so it lives beside the nightly schedule and shares its row.

Revision ID: 20260928_0007
Revises: 20260814_0006
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa


revision = "20260928_0007"
down_revision = "20260814_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("import_automation") as batch:
        batch.add_column(
            sa.Column("check_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column("check_interval_minutes", sa.Integer(), nullable=False, server_default="15")
        )
        batch.add_column(sa.Column("last_check_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("last_check_message", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("import_automation") as batch:
        batch.drop_column("last_check_message")
        batch.drop_column("last_check_at")
        batch.drop_column("check_interval_minutes")
        batch.drop_column("check_enabled")
