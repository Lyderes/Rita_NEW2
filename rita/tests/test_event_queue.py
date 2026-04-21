from __future__ import annotations

from pathlib import Path

from src.integrations.event_queue import LocalEventQueue


def test_enqueue_adds_event_to_queue(tmp_path: Path) -> None:
    queue = LocalEventQueue(tmp_path / "events.jsonl")

    ok = queue.enqueue({"event_type": "distress", "severity": "medium"})

    assert ok is True
    pending = queue.read_pending()
    assert len(pending) == 1
    assert pending[0]["event_type"] == "distress"


def test_retry_successful_empties_queue(tmp_path: Path) -> None:
    queue = LocalEventQueue(tmp_path / "events.jsonl")
    queue.enqueue({"id": 1, "event_type": "fall"})
    queue.enqueue({"id": 2, "event_type": "emergency"})

    sent_order: list[int] = []

    def sender(event: dict[str, object]) -> bool:
        sent_order.append(int(event["id"]))
        return True

    sent, remaining = queue.retry_pending(sender)

    assert sent == 2
    assert remaining == 0
    assert sent_order == [1, 2]
    assert queue.read_pending() == []


def test_retry_failed_keeps_queue(tmp_path: Path) -> None:
    queue = LocalEventQueue(tmp_path / "events.jsonl")
    queue.enqueue({"id": 1, "event_type": "fall"})
    queue.enqueue({"id": 2, "event_type": "emergency"})

    def sender(_event: dict[str, object]) -> bool:
        return False

    sent, remaining = queue.retry_pending(sender)

    assert sent == 0
    assert remaining == 2
    pending = queue.read_pending()
    assert [int(item["id"]) for item in pending] == [1, 2]
