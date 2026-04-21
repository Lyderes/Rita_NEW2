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
from app.services.alert_escalation_service import run_alert_escalation_once  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run pending-alert escalation monitor")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="Loop interval in seconds when not using --once",
    )
    parser.add_argument(
        "--pending-threshold-minutes",
        type=int,
        default=10,
        help="Minutes a pending alert can stay open before escalation",
    )
    parser.add_argument(
        "--source",
        default="alert-escalation-monitor",
        help="source identifier used for escalation audit entries",
    )
    return parser.parse_args()


def _run_cycle(args: argparse.Namespace) -> int:
    now = datetime.now(UTC)
    db = SessionLocal()
    try:
        result = run_alert_escalation_once(
            db,
            now=now,
            pending_threshold_minutes=args.pending_threshold_minutes,
            source=args.source,
        )
    finally:
        db.close()

    payload = {
        "at": now.isoformat(),
        "scanned_pending_alerts": result.scanned_pending_alerts,
        "overdue_pending_alerts": result.overdue_pending_alerts,
        "escalated_alerts": result.escalated_alerts,
        "already_escalated_alerts": result.already_escalated_alerts,
        "skipped_recent_pending_alerts": result.skipped_recent_pending_alerts,
        "notification_jobs_created": result.notification_jobs_created,
        "pending_threshold_minutes": args.pending_threshold_minutes,
        "source": args.source,
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def main() -> int:
    args = _parse_args()

    if args.once:
        return _run_cycle(args)

    print(
        f"alert-escalation-monitor loop started interval={args.interval_seconds}s "
        f"pending_threshold={args.pending_threshold_minutes}m"
    )
    while True:
        _run_cycle(args)
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
