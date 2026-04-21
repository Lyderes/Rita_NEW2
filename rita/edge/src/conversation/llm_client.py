from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, runtime_checkable

import requests

_ASSISTANT_PREFIX_RE = re.compile(r"^(?:RITA\s*:\s*)+", re.IGNORECASE)
_GENERIC_SPEAKER_RE = re.compile(
    r"^([A-Za-zÁÉÍÓÚáéíóúÑñ]{2,}(?:\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]{2,}){0,2})\s*:\s*(.*)$"
)
_USER_SPEAKER_LABELS = {"usuario", "tu", "tú", "user"}
_NON_USER_LABELS = {"rita", "nota", "consejo", "importante", "respuesta"}


@dataclass(slots=True)
class LlmResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0

@runtime_checkable
class LlmProvider(Protocol):
    """Minimal interface for LLM backend."""

    def generate(self, prompt: str) -> LlmResponse: ...


def _strip_assistant_prefix(text: str) -> str:
    return _ASSISTANT_PREFIX_RE.sub("", text).strip()


def _is_user_like_speaker(label: str, user_name: str | None) -> bool:
    normalized = label.strip().casefold()
    if normalized in _USER_SPEAKER_LABELS:
        return True
    if user_name and normalized == user_name.strip().casefold():
        return True
    if normalized in _NON_USER_LABELS:
        return False
    return normalized != "rita"


def sanitize_llm_response(content: str, user_name: str | None = None) -> str:
    """Keep only the first assistant answer and discard synthetic dialogue."""
    lines = [line.strip() for line in str(content).splitlines() if line.strip()]
    if not lines:
        return ""

    kept_lines: list[str] = []
    started = False

    for raw_line in lines:
        speaker_match = _GENERIC_SPEAKER_RE.match(raw_line)
        if speaker_match:
            label, remainder = speaker_match.groups()
            if label.strip().casefold() == "rita":
                cleaned = _strip_assistant_prefix(raw_line)
                if cleaned:
                    kept_lines.append(cleaned)
                    started = True
                continue

            if _is_user_like_speaker(label, user_name):
                if started or kept_lines:
                    break
                continue

        cleaned = _strip_assistant_prefix(raw_line)
        if not cleaned:
            continue
        kept_lines.append(cleaned)
        started = True

    return "\n".join(kept_lines).strip()


@dataclass(slots=True)
class LlamaCppClient:
    base_url: str = "http://localhost:8001"
    chat_endpoint: str = "/v1/chat/completions"
    model: str = "model"
    timeout_s: int = 20
    temperature: float = 0.2
    max_tokens: int = 64

    def generate(self, prompt: str) -> str:
        base = self.base_url.rstrip("/")
        endpoint = self.chat_endpoint.strip()
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            url = endpoint
        else:
            if not endpoint.startswith("/"):
                endpoint = f"/{endpoint}"
            url = f"{base}{endpoint}"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
            "usage": True, # Ensure usage is returned
        }

        try:
            response = requests.post(url, json=payload, timeout=(10, self.timeout_s))
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise LlmProviderError(f"Fallo de conexion con llama.cpp server: {exc}") from exc
        except ValueError as exc:
            raise LlmProviderError("Respuesta JSON invalida desde llama.cpp server.") from exc

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlmProviderError("llama.cpp server devolvio una respuesta vacia.")

        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else None
        content = ""
        if isinstance(message, dict):
            content = str(message.get("content", "")).strip()

        if not content:
            raise LlmProviderError("llama.cpp server devolvio una respuesta vacia.")

        lines = [line.rstrip() for line in content.splitlines()]
        normalized = "\n".join(line for line in lines if line.strip())
        
        usage = data.get("usage", {})
        return LlmResponse(
            content=normalized or content,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0)
        )
