"""backfill legacy plaintext device tokens

Revision ID: b6f4d1c2e3a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-13 13:00:00.000000

"""
from __future__ import annotations

import hashlib

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = "b6f4d1c2e3a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _is_sha256_hex(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in value)


def backfill_legacy_plaintext_device_tokens(connection: Connection) -> int:
    """Hash legacy plaintext tokens stored in device_token_hash after rename migration.

    Legacy rows may contain plaintext because the column was renamed from device_token.
    This backfill preserves compatibility for already provisioned devices.
    """
    rows = connection.execute(
        sa.text(
            """
            SELECT id, device_token_hash
            FROM devices
            WHERE device_token_hash IS NOT NULL
            """
        )
    ).fetchall()

    updated = 0
    for row in rows:
        device_id = int(row.id)
        stored_value = str(row.device_token_hash)
        if _is_sha256_hex(stored_value):
            continue

        hashed = hashlib.sha256(stored_value.encode()).hexdigest()
        connection.execute(
            sa.text(
                """
                UPDATE devices
                SET device_token_hash = :hashed
                WHERE id = :device_id
                """
            ),
            {"hashed": hashed, "device_id": device_id},
        )
        updated += 1

    return updated


def upgrade() -> None:
    connection = op.get_bind()
    backfill_legacy_plaintext_device_tokens(connection)


def downgrade() -> None:
    # Irreversible data migration: hashed values cannot be restored to plaintext.
    # Schema remains unchanged in this revision, only data semantics are updated.
    pass
