from __future__ import annotations

import pytest

from src.config import RitaConfig
from src.conversation.voice_assistant import VoiceAssistant, send_heartbeat_to_backend


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FailIfCalledLlm:
    def generate(self, _prompt: str) -> str:
        raise AssertionError("LLM no deberia llamarse en intents simples")


def test_send_heartbeat_builds_expected_url(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []

    def _post(url: str, headers: dict[str, str] | None = None, timeout: int = 0):
        calls.append((url, timeout))
        return _Response(200)

    monkeypatch.setattr("src.conversation.voice_assistant.requests.post", _post)

    ok = send_heartbeat_to_backend(
        heartbeat_url="http://localhost:8000/devices/{device_code}/heartbeat",
        device_code="rita-edge-001",
        timeout_s=2,
    )

    assert ok is True
    assert calls == [("http://localhost:8000/devices/rita-edge-001/heartbeat", 2)]


def test_heartbeat_failure_does_not_break_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.conversation.voice_assistant.send_heartbeat_to_backend",
        lambda **_kwargs: False,
    )

    config = RitaConfig(
        backend_retry_on_startup=False,
        backend_heartbeat_on_startup=False,
        backend_heartbeat_after_turn=True,
    )
    assistant = VoiceAssistant(config=config, text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    result = assistant.run_turn("hola")

    assert result.should_exit is False
    assert result.rita_text != ""


def test_heartbeat_runs_on_startup_and_after_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, int]] = []

    def _heartbeat(
        *,
        heartbeat_url: str,
        device_code: str,
        device_token: str | None = None,
        timeout_s: int = 3,
    ) -> bool:
        calls.append((heartbeat_url, device_code, timeout_s))
        return True

    monkeypatch.setattr("src.conversation.voice_assistant.send_heartbeat_to_backend", _heartbeat)

    config = RitaConfig(
        backend_retry_on_startup=False,
        backend_heartbeat_on_startup=True,
        backend_heartbeat_after_turn=True,
        backend_heartbeat_timeout_s=1,
    )
    assistant = VoiceAssistant(config=config, text_mode=True)
    assistant.llm = _FailIfCalledLlm()

    assistant.run_turn("hola")

    assert len(calls) == 2
    assert calls[0][1] == config.backend_device_code
    assert calls[1][1] == config.backend_device_code
