from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import _parse_allowed_origins


DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5180",
    "http://127.0.0.1:5180",
    "http://localhost:5190",
    "http://127.0.0.1:5190",
]


def test_parse_allowed_origins_defaults_for_none_blank_or_empty_list() -> None:
    assert _parse_allowed_origins(None) == DEFAULT_ORIGINS
    assert _parse_allowed_origins("") == DEFAULT_ORIGINS
    assert _parse_allowed_origins("   ") == DEFAULT_ORIGINS
    assert _parse_allowed_origins(" , , ") == DEFAULT_ORIGINS


def test_parse_allowed_origins_strips_spaces_and_deduplicates() -> None:
    parsed = _parse_allowed_origins(
        " http://localhost:3000 , http://127.0.0.1:3000 , http://localhost:3000 "
    )
    assert parsed == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_parse_allowed_origins_allows_only_explicit_star() -> None:
    assert _parse_allowed_origins("*") == ["*"]
    with pytest.raises(ValueError, match="cannot mix"):
        _parse_allowed_origins("*, http://localhost:3000")


def test_alembic_check_has_no_pending_operations(tmp_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    existing_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(backend_root) if not existing_path else f"{str(backend_root)}{os.pathsep}{existing_path}"
    test_db_path = tmp_path / "alembic_check.db"
    env["DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"

    upgrade_result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_root,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        env=env,
        check=False,
    )
    assert (
        upgrade_result.returncode == 0
    ), f"STDOUT:\n{upgrade_result.stdout}\nSTDERR:\n{upgrade_result.stderr}"

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=backend_root,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    combined = f"{result.stdout}\n{result.stderr}"
    assert "No new upgrade operations detected." in combined
