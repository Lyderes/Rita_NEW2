from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class RiskPattern:
    phrase: str
    regex: str


DEFAULT_RISK_PATTERNS = (
    RiskPattern(phrase="socorro", regex=r"\bsocorro\b"),
    RiskPattern(phrase="me he caido", regex=r"me\s+he\s+ca[ií]do"),
    RiskPattern(phrase="me cai", regex=r"\bme\s+ca[ií]\b"),
    RiskPattern(phrase="ayuda", regex=r"\bayuda\b"),
    RiskPattern(phrase="me encuentro mal", regex=r"me\s+encuentro\s+mal"),
    RiskPattern(phrase="llama a alguien", regex=r"llama\s+a\s+alguien"),
)


@dataclass(slots=True)
class RiskMatch:
    phrase: str
    matched_text: str


class KeywordDetector:
    """Regex detector adapted from RITA's current keyword detector approach.

    We keep only patterns relevant to RITA MVP and avoid legacy cloud rules
    and check-in event coupling to keep architecture clean.
    """

    def __init__(self, patterns: tuple[RiskPattern, ...] = DEFAULT_RISK_PATTERNS) -> None:
        self._patterns = [
            (entry.phrase, re.compile(entry.regex, re.IGNORECASE))
            for entry in patterns
        ]

    def detect(self, text: str) -> RiskMatch | None:
        normalized = text.strip()
        for phrase, compiled in self._patterns:
            match = compiled.search(normalized)
            if match:
                return RiskMatch(phrase=phrase, matched_text=match.group(0))
        return None

    @staticmethod
    def emergency_response() -> str:
        return (
            "Entendido. Detecto que puedes necesitar ayuda inmediata. "
            "Me quedo contigo. Si puedes, llama ahora a un familiar o al 112."
        )
