"""Create secure device registry.

Revision ID: 20260724_0001
Revises:
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa


revision = "20260724_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    legacy_table = "devices" if "devices" in inspector.get_table_names() else None
    if legacy_table:
        legacy_columns = {column["name"] for column in inspector.get_columns(legacy_table)}
        if "credentials_encrypted" in legacy_columns:
            return
        op.rename_table("devices", "devices_legacy")
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("credentials_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("model", sa.String(length=50), nullable=True),
        sa.Column("device_type", sa.String(length=50), nullable=False, server_default="hikvision"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    if legacy_table:
        op.execute(
            """
            INSERT INTO devices (id, name, host, port, username, credentials_encrypted, model, device_type, enabled)
            SELECT id, name, ip, 80, username, '', model, 'hikvision', 0 FROM devices_legacy
            """
        )
        op.drop_table("devices_legacy")


def downgrade() -> None:
    op.drop_table("devices")
