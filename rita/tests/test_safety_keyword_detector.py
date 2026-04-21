from __future__ import annotations

from src.safety.keyword_detector import KeywordDetector


def test_detects_requested_risk_phrases() -> None:
    detector = KeywordDetector()
    match = detector.detect("Por favor ayuda, me encuentro mal")
    assert match is not None
    assert match.phrase in {"ayuda", "me encuentro mal"}


def test_no_false_positive() -> None:
    detector = KeywordDetector()
    assert detector.detect("Hoy he desayunado bien y estoy tranquilo") is None
