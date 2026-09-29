"""Let the directory hold visitors that exist only in Sigma.

A visitor registered in Sigma is often never enrolled on a facial: they are let in
by the porter, who then needs to find them — host unit, document, face — in the same
search as everybody else. Until now every row in ``residents`` was an enrollment on
some device, so there was nowhere to put them.

``device_id`` becomes nullable: ``NULL`` is a person known only from Sigma.
``sigma_id`` is Sigma's own identifier, which is what recognises that same visitor
on the next import — a visitor usually has no ``commonEnroll`` to go by.

Revision ID: 20260928_0009
Revises: 20260928_0008
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa


revision = "20260928_0009"
down_revision = "20260928_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("residents") as batch:
        batch.alter_column("device_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("sigma_id", sa.Integer(), nullable=True))
        batch.create_index("ix_residents_sigma_id", ["sigma_id"])


def downgrade() -> None:
    op.execute("DELETE FROM residents WHERE device_id IS NULL")
    with op.batch_alter_table("residents") as batch:
        batch.drop_index("ix_residents_sigma_id")
        batch.drop_column("sigma_id")
        batch.alter_column("device_id", existing_type=sa.Integer(), nullable=False)
