from __future__ import annotations

import json
import sys
from pathlib import Path

from src.stt.vosk_transcriber import VoskTranscriber


class _FakeModel:
    def __init__(self, _path: str) -> None:
        pass


class _FakeRecognizer:
    def __init__(self, _model, _sample_rate: int) -> None:
        self.words_enabled = False

    def SetWords(self, enabled: bool) -> None:
        self.words_enabled = enabled

    def AcceptWaveform(self, _data: bytes) -> bool:
        return True

    def FinalResult(self) -> str:
        return json.dumps({"text": "hola rita"})


class _FakeVosk:
    Model = _FakeModel
    KaldiRecognizer = _FakeRecognizer


def test_vosk_transcriber_with_fake_backend(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "vosk", _FakeVosk)

    wav_path = tmp_path / "sample.wav"
    import wave

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 8000)

    model_dir = tmp_path / "model"
    model_dir.mkdir()

    transcriber = VoskTranscriber(model_path=model_dir, sample_rate=16000)
    result = transcriber.transcribe_file(wav_path)
    assert result.text == "hola rita"
