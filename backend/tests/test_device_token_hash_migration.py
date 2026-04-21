from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, text


def _load_migration_module():
    backend_path = Path(__file__).resolve().parents[1]
    migration_path = backend_path / "alembic" / "versions" / "b6f4d1c2e3a7_backfill_legacy_device_tokens.py"
    spec = importlib.util.spec_from_file_location("backfill_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backfill_hashes_legacy_plaintext_tokens() -> None:
    module = _load_migration_module()
    engine = create_engine("sqlite+pysqlite://", future=True)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE devices (
                    id INTEGER PRIMARY KEY,
                    device_token_hash VARCHAR(64)
                )
                """
            )
        )
        conn.execute(
            text("INSERT INTO devices (id, device_token_hash) VALUES (1, :token)"),
            {"token": "legacy-token-001"},
        )

        updated = module.backfill_legacy_plaintext_device_tokens(conn)
        stored = conn.execute(
            text("SELECT device_token_hash FROM devices WHERE id = 1")
        ).scalar_one()

    assert updated == 1
    assert stored == hashlib.sha256("legacy-token-001".encode()).hexdigest()


def test_backfill_keeps_existing_sha256_hashes_unchanged() -> None:
    module = _load_migration_module()
    engine = create_engine("sqlite+pysqlite://", future=True)
    existing_hash = hashlib.sha256("already-hashed-token".encode()).hexdigest()

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE devices (
                    id INTEGER PRIMARY KEY,
                    device_token_hash VARCHAR(64)
                )
                """
            )
        )
        conn.execute(
            text("INSERT INTO devices (id, device_token_hash) VALUES (1, :token)"),
            {"token": existing_hash},
        )

        updated = module.backfill_legacy_plaintext_device_tokens(conn)
        stored = conn.execute(
            text("SELECT device_token_hash FROM devices WHERE id = 1")
        ).scalar_one()

    assert updated == 0
    assert stored == existing_hash
