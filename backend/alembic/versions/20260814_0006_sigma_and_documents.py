"""Separate CPF from RG, and remember the Sigma integration.

The Sigma register keeps the two documents apart — `federalRegister` is the CPF and
`nationalId` is the RG — and the porter identifying someone reads whichever one they
are holding. A single `document` column could only ever carry one of them.

The rename loses nothing: no enrollment had a document recorded when this ran.

Revision ID: 20260814_0006
Revises: 20260811_0005
Create Date: 2026-08-14
"""
from alembic import op
import sqlalchemy as sa


revision = "20260814_0006"
down_revision = "20260811_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("residents") as batch:
        batch.alter_column("document", new_column_name="cpf")
        batch.add_column(sa.Column("rg", sa.String(length=32), nullable=True))

    op.create_table(
        "sigma_integration",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Cifrado com a mesma chave das senhas das faciais. Um token de integração
        # abre a base inteira do cliente no Sigma; em claro no banco, qualquer cópia
        # do arquivo o levaria junto.
        sa.Column("token_encrypted", sa.String(length=2048), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("last_import_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=16), nullable=True),
        sa.Column("last_message", sa.String(length=1024), nullable=True),
    )
    op.execute("INSERT INTO sigma_integration (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("sigma_integration")
    with op.batch_alter_table("residents") as batch:
        batch.drop_column("rg")
        batch.alter_column("cpf", new_column_name="document")
