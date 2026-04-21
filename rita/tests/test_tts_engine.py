from __future__ import annotations

import sys
import types

from src.tts.engine import TtsEngine


class _Voice:
    def __init__(self, voice_id: str, name: str, languages: list[str] | None = None) -> None:
        self.id = voice_id
        self.name = name
        self.languages = languages or []


class _MockEngine:
    def __init__(self) -> None:
        self._props = {
            "voices": [_Voice("es-ES", "Spanish voice", ["es_ES"])],
        }
        self.spoken: list[str] = []

    def setProperty(self, key: str, value):
        self._props[key] = value

    def getProperty(self, key: str):
        return self._props[key]

    def say(self, text: str) -> None:
        self.spoken.append(text)

    def runAndWait(self) -> None:
        return None


class _MockPyttsx3(types.SimpleNamespace):
    def init(self):
        return _MockEngine()


def test_tts_speaks_with_mocked_engine(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pyttsx3", _MockPyttsx3())
    engine = TtsEngine(rate=150, volume=0.9)
    ok = engine.speak("Hola")
    assert ok is True
