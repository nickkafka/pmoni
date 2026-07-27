"""Create the resident directory synced from devices.

Revision ID: 20260727_0002
Revises: 20260724_0001
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa


revision = "20260727_0002"
down_revision = "20260724_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "residents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_no", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("apartment", sa.String(length=32), nullable=True),
        sa.Column("block", sa.String(length=32), nullable=True),
        sa.Column("photo", sa.LargeBinary(), nullable=True),
        sa.Column("photo_reference", sa.String(length=256), nullable=True),
        sa.Column("source_device_id", sa.Integer(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_residents_employee_no", "residents", ["employee_no"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_residents_employee_no", table_name="residents")
    op.drop_table("residents")
