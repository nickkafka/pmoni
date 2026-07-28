"""Key each enrollment by the device that issued its identifier.

Identifiers are only unique inside one device: two devices enrolled separately
give the same number to different people, which made an event show the photo of
somebody else. Locations already typed are preserved on the enrollment they were
recorded against.

Revision ID: 20260728_0003
Revises: 20260727_0002
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa


revision = "20260728_0003"
down_revision = "20260727_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("residents", "residents_by_identifier")
    # SQLite keeps the index attached to the renamed table, so the name stays taken.
    op.drop_index("ix_residents_employee_no", table_name="residents_by_identifier")
    op.create_table(
        "residents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("employee_no", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("apartment", sa.String(length=32), nullable=True),
        sa.Column("block", sa.String(length=32), nullable=True),
        sa.Column("photo", sa.LargeBinary(), nullable=True),
        sa.Column("photo_reference", sa.String(length=256), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("device_id", "employee_no", name="uq_residents_device_employee"),
    )
    op.create_index("ix_residents_device_id", "residents", ["device_id"])
    op.create_index("ix_residents_employee_no", "residents", ["employee_no"])
    # Rows without a source device cannot be attributed to any enrollment; the next
    # synchronisation recreates them from the device itself.
    op.execute(
        """
        INSERT INTO residents (device_id, employee_no, name, apartment, block, photo, photo_reference, synced_at)
        SELECT source_device_id, employee_no, name, apartment, block, photo, photo_reference, synced_at
        FROM residents_by_identifier
        WHERE source_device_id IS NOT NULL
        """
    )
    op.drop_table("residents_by_identifier")


def downgrade() -> None:
    op.drop_index("ix_residents_employee_no", table_name="residents")
    op.drop_index("ix_residents_device_id", table_name="residents")
    op.drop_table("residents")
