from __future__ import annotations

import json
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

class SttError(RuntimeError):
    """Raised when STT cannot transcribe input audio."""


@dataclass(slots=True)
class Transcription:
    text: str


class VoskTranscriber:
    """Offline STT backed by a local Vosk model."""

    def __init__(self, model_path: Path, sample_rate: int = 16000) -> None:
        if not model_path.exists():
            raise FileNotFoundError(f"Modelo Vosk no encontrado: {model_path}")
        self.sample_rate = sample_rate

        try:
            from vosk import Model  # type: ignore[import]
        except Exception as exc:
            raise SttError(
                "Vosk no esta instalado o no se pudo importar. Ejecuta pip install -r requirements.txt"
            ) from exc

        try:
            self._model = Model(str(model_path))
        except Exception as exc:
            raise SttError(f"No se pudo cargar el modelo Vosk: {exc}") from exc

    def transcribe_file(self, wav_path: Path) -> Transcription:
        if not wav_path.exists():
            raise SttError(f"Archivo de audio no encontrado: {wav_path}")

        try:
            from vosk import KaldiRecognizer  # type: ignore[import]
        except Exception as exc:
            raise SttError("No se pudo importar KaldiRecognizer de vosk.") from exc

        recognizer: Any = KaldiRecognizer(self._model, self.sample_rate)
        recognizer.SetWords(True)

        try:
            with wave.open(str(wav_path), "rb") as wav_file:
                wav_rate = wav_file.getframerate()
                if wav_rate != self.sample_rate:
                    raise SttError(
                        f"Sample rate invalido ({wav_rate}). Esperado: {self.sample_rate}."
                    )

                while True:
                    data = wav_file.readframes(4000)
                    if not data:
                        break
                    recognizer.AcceptWaveform(data)
        except SttError:
            raise
        except Exception as exc:
            raise SttError(f"No se pudo procesar el WAV para STT: {exc}") from exc

        try:
            result = json.loads(recognizer.FinalResult())
        except Exception as exc:
            raise SttError(f"Respuesta invalida del reconocedor Vosk: {exc}") from exc

        text = str(result.get("text", "")).strip()
        return Transcription(text=text)
