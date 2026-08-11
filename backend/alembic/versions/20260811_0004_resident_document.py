"""Hold the document of a resident alongside the apartment.

The porter needs to identify someone whose face was not recognised, and a document
is what that person carries. Like the apartment, it does not exist on the access
equipment: it is maintained inside pMoni until Sigma supplies it.

Revision ID: 20260811_0004
Revises: 20260728_0003
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa


revision = "20260811_0004"
down_revision = "20260728_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("residents", sa.Column("document", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("residents", "document")
