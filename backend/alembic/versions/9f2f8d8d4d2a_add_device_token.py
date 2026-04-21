"""add device token

Revision ID: 9f2f8d8d4d2a
Revises: 413f16528bb1
Create Date: 2026-03-13 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f2f8d8d4d2a"
down_revision = "413f16528bb1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("device_token", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_column("device_token")
