from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests

from src.conversation.voice_assistant import build_backend_event, send_backend_event_payload
from src.integrations.event_queue import LocalEventQueue


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _make_event(event_type: str, user_text: str) -> dict[str, object]:
    return build_backend_event(
        event_type=event_type,
        severity="low" if event_type == "checkin" else "high",
        user_text=user_text,
        rita_text="respuesta de prueba",
        payload_json={"origin": "voice", "timestamp": "2026-03-11T00:00:00Z"},
        device_code="rita-edge-001",
    )


def test_case_1_backend_up_queue_stays_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    queue = LocalEventQueue(tmp_path / "queue.jsonl")
    event = _make_event("checkin", "estoy bien")

    assert json.dumps(event)

    def _post_ok(
        url: str,
        json: dict[str, object],
        headers: dict[str, str] | None = None,
        timeout: int = 0,
    ) -> _Response:  # noqa: A002
        assert url == "http://localhost:8000/events"
        assert isinstance(json, dict)
        assert headers is None
        assert timeout == 1
        return _Response(200)

    monkeypatch.setattr("src.conversation.voice_assistant.requests.post", _post_ok)

    ok = send_backend_event_payload(
        event,
        backend_url="http://localhost:8000/events",
        timeout_s=1,
    )

    assert ok is True
    assert queue.read_pending() == []


def test_case_2_backend_down_event_saved_in_jsonl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    queue = LocalEventQueue(tmp_path / "queue.jsonl")
    event_1 = _make_event("fall", "me he caido")
    event_2 = _make_event("emergency", "ayuda urgente")

    def _post_down(
        url: str,
        json: dict[str, object],
        headers: dict[str, str] | None = None,
        timeout: int = 0,
    ) -> _Response:  # noqa: A002
        assert url == "http://127.0.0.1:9999/events"
        assert headers is None
        raise requests.RequestException("backend caido")

    monkeypatch.setattr("src.conversation.voice_assistant.requests.post", _post_down)

    ok = send_backend_event_payload(
        event_1,
        backend_url="http://127.0.0.1:9999/events",
        timeout_s=1,
    )
    if not ok:
        assert queue.enqueue(event_1) is True
        assert queue.enqueue(event_2) is True

    assert ok is False
    assert queue.path.exists() is True

    lines = queue.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event_type"] == "fall"
    assert json.loads(lines[1])["event_type"] == "emergency"


def test_case_3_backend_back_retry_drains_fifo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    queue = LocalEventQueue(tmp_path / "queue.jsonl")
    event_1 = _make_event("fall", "evento 1")
    event_2 = _make_event("emergency", "evento 2")
    assert queue.enqueue(event_1) is True
    assert queue.enqueue(event_2) is True

    sent_payloads: list[dict[str, object]] = []

    def _post_ok(
        url: str,
        json: dict[str, object],
        headers: dict[str, str] | None = None,
        timeout: int = 0,
    ) -> _Response:  # noqa: A002
        assert url == "http://localhost:8000/events"
        assert headers is None
        sent_payloads.append(json)
        return _Response(200)

    monkeypatch.setattr("src.conversation.voice_assistant.requests.post", _post_ok)

    sent, remaining = queue.retry_pending(
        lambda event: send_backend_event_payload(
            event,
            backend_url="http://localhost:8000/events",
            timeout_s=1,
        )
    )

    assert sent == 2
    assert remaining == 0
    assert queue.read_pending() == []
    assert sent_payloads == [event_1, event_2]
