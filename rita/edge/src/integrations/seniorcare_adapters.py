"""Functional adapters for RITA voice components.

This module keeps a compatibility layer so existing imports using legacy
SeniorCare symbols continue working while new code uses RITA naming.
"""

from __future__ import annotations

from pathlib import Path

from src.audio.recorder import AudioRecorder
from src.safety.keyword_detector import KeywordDetector
from src.stt.vosk_transcriber import VoskTranscriber
from src.tts.engine import TtsEngine


class RitaVoiceStack:
    """Container exposing reusable voice components with stable initialization."""

    def __init__(
        self,
        recordings_dir: Path,
        model_path: Path,
        sample_rate: int,
        silence_amplitude: float,
        tts_rate: int,
        tts_volume: float,
    ) -> None:
        self.recorder = AudioRecorder(
            recordings_dir=recordings_dir,
            sample_rate=sample_rate,
            silence_amplitude=silence_amplitude,
        )
        self.stt = VoskTranscriber(model_path=model_path, sample_rate=sample_rate)
        self.tts = TtsEngine(rate=tts_rate, volume=tts_volume)
        self.risk_detector = KeywordDetector()


def build_rita_voice_stack(
    recordings_dir: Path,
    model_path: Path,
    sample_rate: int,
    silence_amplitude: float,
    tts_rate: int,
    tts_volume: float,
) -> RitaVoiceStack:
    return RitaVoiceStack(
        recordings_dir=recordings_dir,
        model_path=model_path,
        sample_rate=sample_rate,
        silence_amplitude=silence_amplitude,
        tts_rate=tts_rate,
        tts_volume=tts_volume,
    )


# Backward-compatible aliases for legacy imports.
SeniorCareVoiceStack = RitaVoiceStack
build_seniorcare_voice_stack = build_rita_voice_stack
