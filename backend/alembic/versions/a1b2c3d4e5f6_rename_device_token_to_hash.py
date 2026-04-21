"""rename device_token to device_token_hash

Revision ID: a1b2c3d4e5f6
Revises: 9f2f8d8d4d2a
Create Date: 2026-03-13 12:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9f2f8d8d4d2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.alter_column(
            "device_token",
            new_column_name="device_token_hash",
            existing_type=sa.String(length=255),
            existing_nullable=True,
            type_=sa.String(length=64),
        )


def downgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.alter_column(
            "device_token_hash",
            new_column_name="device_token",
            existing_type=sa.String(length=64),
            existing_nullable=True,
            type_=sa.String(length=255),
        )
