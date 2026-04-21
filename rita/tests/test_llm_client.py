from __future__ import annotations

from typing import Any

import requests

from src.conversation.llm_client import (
    LlamaCppClient,
    LlmProviderError,
    sanitize_llm_response,
)


class _MockResponse:
    def __init__(
        self,
        payload: dict[str, Any],
        status_code: int = 200,
        iter_lines_data: list[str] | None = None,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self._iter_lines_data = iter_lines_data or []

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError("http error")

    def json(self) -> dict[str, Any]:
        return self._payload

    def iter_lines(self, decode_unicode: bool = False):
        for item in self._iter_lines_data:
            if decode_unicode:
                yield item
            else:
                yield item.encode("utf-8")


def test_sanitize_keeps_only_first_assistant_response() -> None:
    raw = "RITA: Buenos días.\nDavid: Hola\nRITA: ¿Cómo estás?"

    result = sanitize_llm_response(raw, user_name="David")

    assert result == "Buenos días."


def test_sanitize_cuts_fictitious_multiturn_dialogue() -> None:
    raw = "Te propongo dar un paseo corto.\nUsuario: vale\nRITA: también puedes leer un rato"

    result = sanitize_llm_response(raw)

    assert result == "Te propongo dar un paseo corto."


def test_sanitize_removes_duplicated_rita_prefix() -> None:
    raw = "RITA: RITA: Podemos hacer estiramientos suaves hoy."

    result = sanitize_llm_response(raw)

    assert result == "Podemos hacer estiramientos suaves hoy."


def test_llama_cpp_parses_openai_chat_completion(monkeypatch) -> None:
    def _mock_post(*_args, **_kwargs):
        return _MockResponse({"choices": [{"message": {"content": "Hola desde llama"}}]})

    monkeypatch.setattr(requests, "post", _mock_post)
    client = LlamaCppClient(
        base_url="http://localhost:8001",
        chat_endpoint="/v1/chat/completions",
        model="model",
    )

    result = client.generate("hola")
    assert result == "Hola desde llama"


def test_llama_cpp_builds_request_payload(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _mock_post(url: str, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        captured["timeout"] = kwargs.get("timeout")
        return _MockResponse({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(requests, "post", _mock_post)
    client = LlamaCppClient(
        base_url="http://localhost:8001",
        chat_endpoint="/v1/chat/completions",
        model="model",
        timeout_s=25,
        temperature=0.3,
        max_tokens=80,
    )

    _ = client.generate("hola")

    assert captured["url"] == "http://localhost:8001/v1/chat/completions"
    assert captured["timeout"] == (10, 25)
    assert captured["json"]["model"] == "model"
    assert captured["json"]["temperature"] == 0.3
    assert captured["json"]["max_tokens"] == 80
    assert captured["json"]["stream"] is False
    assert captured["json"]["messages"][0]["role"] == "user"
    assert captured["json"]["messages"][0]["content"] == "hola"


def test_llama_cpp_error_is_controlled(monkeypatch) -> None:
    def _mock_post(*_args, **_kwargs):
        raise requests.ConnectionError("boom-llama")

    monkeypatch.setattr(requests, "post", _mock_post)
    client = LlamaCppClient(base_url="http://localhost:8001", model="model")

    try:
        client.generate("hola")
        assert False, "Expected LlmProviderError"
    except LlmProviderError:
        assert True


def test_llama_cpp_default_timeout_is_20() -> None:
    client = LlamaCppClient(base_url="http://localhost:8001", model="model")
    assert client.timeout_s == 20


def test_llama_cpp_invalid_json_is_controlled(monkeypatch) -> None:
    class _BadResponse(_MockResponse):
        def json(self):
            raise ValueError("invalid json")

    def _mock_post(*_args, **_kwargs):
        return _BadResponse({})

    monkeypatch.setattr(requests, "post", _mock_post)
    client = LlamaCppClient(base_url="http://localhost:8001", model="model")

    try:
        client.generate("hola")
        assert False, "Expected LlmProviderError"
    except LlmProviderError:
        assert True
