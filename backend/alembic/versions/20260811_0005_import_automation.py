"""Remember when the daily import should run, and how the last one went.

A single row: there is one condominium per installation and one routine to run.
Keeping it in the database rather than in the environment lets the operator change
the time from the administration screen, without restarting anything.

Revision ID: 20260811_0005
Revises: 20260811_0004
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa


revision = "20260811_0005"
down_revision = "20260811_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_automation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        # Guardado como "HH:MM" no fuso da própria máquina da portaria, que é onde
        # o horário significa alguma coisa para quem o definiu.
        sa.Column("run_at", sa.String(length=5), nullable=False, server_default="03:00"),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_message", sa.String(length=1024), nullable=True),
    )
    # A linha existe desde já, para que ler a configuração nunca precise criá-la.
    op.execute(
        "INSERT INTO import_automation (id, enabled, run_at) VALUES (1, 0, '03:00')"
    )


def downgrade() -> None:
    op.drop_table("import_automation")
