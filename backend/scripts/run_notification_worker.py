from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.services.notification_worker_service import run_notification_worker_once  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run internal notification worker")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="Loop interval in seconds when not using --once",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Max pending jobs processed per cycle",
    )
    parser.add_argument(
        "--base-backoff-seconds",
        type=int,
        default=30,
        help="Base backoff in seconds for retry scheduling",
    )
    return parser.parse_args()


def _run_cycle(args: argparse.Namespace) -> int:
    now = datetime.now(UTC)
    db = SessionLocal()
    try:
        result = run_notification_worker_once(
            db,
            now=now,
            batch_size=args.batch_size,
            base_backoff_seconds=args.base_backoff_seconds,
        )
    finally:
        db.close()

    payload = {
        "at": now.isoformat(),
        "batch_size": args.batch_size,
        "base_backoff_seconds": args.base_backoff_seconds,
        "scanned_eligible_jobs": result.scanned_eligible_jobs,
        "processed_jobs": result.processed_jobs,
        "sent_jobs": result.sent_jobs,
        "rescheduled_jobs": result.rescheduled_jobs,
        "terminal_failed_jobs": result.terminal_failed_jobs,
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def main() -> int:
    args = _parse_args()

    if args.once:
        return _run_cycle(args)

    print(f"notification-worker loop started interval={args.interval_seconds}s batch_size={args.batch_size}")
    while True:
        _run_cycle(args)
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
