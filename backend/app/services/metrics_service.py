from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from threading import Lock

_REQUIRED_COUNTERS = (
    "events_received_total",
    "events_rejected_semantic_total",
    "events_idempotent_replay_total",
    "incidents_created_total",
    "alerts_created_total",
    "device_auth_failed_total",
    "device_forbidden_total",
    "audit_required_failure_total",
)

_lock = Lock()
_counters: dict[str, int] = {name: 0 for name in _REQUIRED_COUNTERS}
_http_requests_total: dict[tuple[str, str, int], int] = defaultdict(int)
_http_duration: dict[str, dict[str, float]] = defaultdict(
    lambda: {"count": 0.0, "total_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "last_ms": 0.0}
)


def increment_counter(name: str, value: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + value


def increment_http_request(method: str, endpoint: str, status_code: int) -> None:
    with _lock:
        _http_requests_total[(method, endpoint, status_code)] += 1


def observe_http_duration(endpoint: str, duration_ms: float) -> None:
    with _lock:
        stats = _http_duration[endpoint]
        count = stats["count"] + 1.0
        stats["count"] = count
        stats["total_ms"] += duration_ms
        stats["last_ms"] = duration_ms
        if count == 1.0:
            stats["min_ms"] = duration_ms
            stats["max_ms"] = duration_ms
        else:
            stats["min_ms"] = min(stats["min_ms"], duration_ms)
            stats["max_ms"] = max(stats["max_ms"], duration_ms)


def get_metrics_snapshot() -> dict[str, object]:
    with _lock:
        counters = {name: _counters.get(name, 0) for name in _REQUIRED_COUNTERS}

        http_requests = [
            {
                "method": method,
                "endpoint": endpoint,
                "status_code": status_code,
                "count": count,
            }
            for (method, endpoint, status_code), count in sorted(
                _http_requests_total.items(), key=lambda x: (x[0][1], x[0][0], x[0][2])
            )
        ]

        duration_summary = []
        for endpoint, stats in sorted(_http_duration.items(), key=lambda x: x[0]):
            count = int(stats["count"])
            total_ms = round(stats["total_ms"], 3)
            avg_ms = round((stats["total_ms"] / stats["count"]) if stats["count"] else 0.0, 3)
            duration_summary.append(
                {
                    "endpoint": endpoint,
                    "count": count,
                    "avg_ms": avg_ms,
                    "min_ms": round(stats["min_ms"], 3),
                    "max_ms": round(stats["max_ms"], 3),
                    "last_ms": round(stats["last_ms"], 3),
                    "total_ms": total_ms,
                }
            )

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "counters": counters,
            "http_requests_total": http_requests,
            "http_request_duration_ms": duration_summary,
        }


def reset_metrics() -> None:
    with _lock:
        for name in _REQUIRED_COUNTERS:
            _counters[name] = 0
        _http_requests_total.clear()
        _http_duration.clear()
