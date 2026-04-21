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
from app.services.heartbeat_monitor_service import run_heartbeat_monitor_once  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run heartbeat monitor for offline devices")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="Loop interval in seconds when not using --once",
    )
    parser.add_argument(
        "--offline-threshold-minutes",
        type=int,
        default=30,
        help="Minutes after last_seen_at to consider device offline",
    )
    parser.add_argument(
        "--no-heartbeat-grace-minutes",
        type=int,
        default=30,
        help="Grace period for devices that never sent heartbeat",
    )
    parser.add_argument(
        "--source",
        default="heartbeat-monitor",
        help="source field for generated device_offline events",
    )
    return parser.parse_args()


def _run_cycle(args: argparse.Namespace) -> int:
    now = datetime.now(UTC)
    db = SessionLocal()
    try:
        result = run_heartbeat_monitor_once(
            db,
            now=now,
            offline_threshold_minutes=args.offline_threshold_minutes,
            no_heartbeat_grace_minutes=args.no_heartbeat_grace_minutes,
            source=args.source,
        )
    finally:
        db.close()

    payload = {
        "at": now.isoformat(),
        "scanned_devices": result.scanned_devices,
        "offline_candidates": result.offline_candidates,
        "events_created": result.events_created,
        "idempotent_replays": result.idempotent_replays,
        "skipped_recent_or_not_due": result.skipped_recent_or_not_due,
        "offline_threshold_minutes": args.offline_threshold_minutes,
        "no_heartbeat_grace_minutes": args.no_heartbeat_grace_minutes,
        "source": args.source,
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def main() -> int:
    args = _parse_args()

    if args.once:
        return _run_cycle(args)

    print(
        f"heartbeat-monitor loop started interval={args.interval_seconds}s "
        f"offline_threshold={args.offline_threshold_minutes}m"
    )
    while True:
        _run_cycle(args)
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
