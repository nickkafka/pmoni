"""Remember whether Sigma still has the person enabled.

A facial keeps letting in somebody the condominium has already disabled in Sigma
until someone removes them from the equipment. The porter watching them pass has no
way to know — and that is exactly the passage worth a second look.

Nullable on purpose: ``NULL`` means Sigma was never asked, or does not know this
person, which is different from Sigma saying they are active.

Revision ID: 20260928_0008
Revises: 20260928_0007
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa


revision = "20260928_0008"
down_revision = "20260928_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("residents") as batch:
        batch.add_column(sa.Column("active", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("residents") as batch:
        batch.drop_column("active")
