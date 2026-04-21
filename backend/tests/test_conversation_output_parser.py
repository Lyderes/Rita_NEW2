"""
Tests para conversation_output_parser.py

Cubre:
  - Respuesta vacía → fallback
  - Texto plano sin JSON → se usa como respuesta
  - JSON en bloque ```json ... ``` → parseo correcto
  - JSON inline sin bloque de código → parseo correcto
  - JSON inválido (malformado) → fallback con texto raw
  - Campos de análisis inválidos → sanitización a defaults
  - Respuesta excesivamente larga → truncación en oración completa
  - memory_candidates: filtrado de tipos inválidos, confianza corregida, máximo 5
"""
from __future__ import annotations

import json
import pytest

from app.services.ai.conversation_output_parser import parse_claude_output
from app.schemas.conversation import ClaudeConversationOutput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_json_response(
    response: str = "Hola, ¿cómo estás?",
    mood: str = "positive",
    risk_level: str = "low",
    **kwargs,
) -> str:
    data = {
        "response": response,
        "analysis": {
            "mood": mood,
            "energy": "normal",
            "risk_level": risk_level,
            "requested_help": False,
            "routine_change_detected": False,
            "signals": [],
            "memory_candidates": [],
            "follow_up_suggestion": None,
            "summary": "",
            **kwargs,
        },
    }
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Casos de respuesta vacía
# ---------------------------------------------------------------------------

def test_empty_string_returns_fallback():
    result = parse_claude_output("")
    assert isinstance(result, ClaudeConversationOutput)
    assert result.response  # tiene texto de fallback
    assert result.analysis is not None


def test_whitespace_only_returns_fallback():
    result = parse_claude_output("   \n  ")
    assert result.response  # fallback, no vacío


# ---------------------------------------------------------------------------
# Texto plano sin JSON
# ---------------------------------------------------------------------------

def test_plain_text_used_as_response():
    text = "Hola María, me alegra hablar contigo hoy."
    result = parse_claude_output(text)
    assert result.response == text
    # Sin JSON → análisis por defecto
    assert result.analysis.risk_level == "low"
    assert result.analysis.mood == "unknown"


def test_plain_text_long_gets_truncated():
    long_text = "Esta es una frase muy larga. " * 100  # mucho más de 800 chars
    result = parse_claude_output(long_text)
    assert len(result.response) <= 800


# ---------------------------------------------------------------------------
# JSON en bloque de código
# ---------------------------------------------------------------------------

def test_json_code_block_parsed_correctly():
    raw = f"```json\n{_valid_json_response()}\n```"
    result = parse_claude_output(raw)
    assert result.response == "Hola, ¿cómo estás?"
    assert result.analysis.mood == "positive"
    assert result.analysis.risk_level == "low"


def test_json_code_block_without_language_tag():
    raw = f"```\n{_valid_json_response(response='Buenos días')}\n```"
    result = parse_claude_output(raw)
    assert result.response == "Buenos días"


# ---------------------------------------------------------------------------
# JSON inline (sin bloque de código)
# ---------------------------------------------------------------------------

def test_inline_json_parsed_correctly():
    raw = _valid_json_response(response="Hola, te escucho.", mood="neutral")
    result = parse_claude_output(raw)
    assert result.response == "Hola, te escucho."
    assert result.analysis.mood == "neutral"


# ---------------------------------------------------------------------------
# JSON malformado
# ---------------------------------------------------------------------------

def test_malformed_json_uses_raw_text_as_response():
    raw = "```json\n{response: 'falta las comillas'}\n```"
    result = parse_claude_output(raw)
    # No debe lanzar excepción
    assert isinstance(result, ClaudeConversationOutput)
    assert result.response  # tiene algo (el texto raw)


def test_json_array_not_dict_returns_fallback():
    raw = json.dumps([1, 2, 3])
    result = parse_claude_output(raw)
    assert result.response  # fallback


# ---------------------------------------------------------------------------
# Sanitización del análisis
# ---------------------------------------------------------------------------

def test_invalid_mood_sanitized_to_unknown():
    data = json.dumps({
        "response": "Hola",
        "analysis": {"mood": "depressed", "risk_level": "low", "energy": "normal"},
    })
    result = parse_claude_output(data)
    assert result.analysis.mood == "unknown"


def test_invalid_risk_level_sanitized_to_low():
    data = json.dumps({
        "response": "Hola",
        "analysis": {"mood": "neutral", "risk_level": "critical", "energy": "normal"},
    })
    result = parse_claude_output(data)
    assert result.analysis.risk_level == "low"


def test_invalid_energy_sanitized_to_unknown():
    data = json.dumps({
        "response": "Hola",
        "analysis": {"mood": "neutral", "risk_level": "low", "energy": "hyper"},
    })
    result = parse_claude_output(data)
    assert result.analysis.energy == "unknown"


# ---------------------------------------------------------------------------
# memory_candidates
# ---------------------------------------------------------------------------

def test_memory_candidates_invalid_type_filtered():
    data = json.dumps({
        "response": "OK",
        "analysis": {
            "mood": "neutral", "risk_level": "low", "energy": "normal",
            "memory_candidates": [
                {"type": "unknown_type", "content": "algo", "confidence": "high"},
                {"type": "person", "content": "Se llama Juan", "confidence": "high"},
            ],
        },
    })
    result = parse_claude_output(data)
    assert len(result.analysis.memory_candidates) == 1
    assert result.analysis.memory_candidates[0].type == "person"


def test_memory_candidates_invalid_confidence_corrected():
    data = json.dumps({
        "response": "OK",
        "analysis": {
            "mood": "neutral", "risk_level": "low", "energy": "normal",
            "memory_candidates": [
                {"type": "health", "content": "Tiene diabetes", "confidence": "super_high"},
            ],
        },
    })
    result = parse_claude_output(data)
    assert result.analysis.memory_candidates[0].confidence == "medium"


def test_memory_candidates_capped_at_five():
    candidates = [
        {"type": "person", "content": f"Hecho {i}", "confidence": "high"}
        for i in range(10)
    ]
    data = json.dumps({
        "response": "OK",
        "analysis": {
            "mood": "neutral", "risk_level": "low", "energy": "normal",
            "memory_candidates": candidates,
        },
    })
    result = parse_claude_output(data)
    assert len(result.analysis.memory_candidates) <= 5


def test_memory_candidates_empty_content_filtered():
    data = json.dumps({
        "response": "OK",
        "analysis": {
            "mood": "neutral", "risk_level": "low", "energy": "normal",
            "memory_candidates": [
                {"type": "health", "content": "   ", "confidence": "high"},
            ],
        },
    })
    result = parse_claude_output(data)
    assert len(result.analysis.memory_candidates) == 0


# ---------------------------------------------------------------------------
# Truncación de respuesta
# ---------------------------------------------------------------------------

def test_response_truncated_at_sentence_boundary():
    long_response = ("Esta es una frase. " * 50).strip()  # bien más de 800 chars
    data = json.dumps({
        "response": long_response,
        "analysis": {"mood": "neutral", "risk_level": "low", "energy": "normal"},
    })
    result = parse_claude_output(data)
    assert len(result.response) <= 800
    # Debe terminar en signo de puntuación
    assert result.response[-1] in ".!?"


def test_response_under_limit_not_truncated():
    short = "Hola, ¿cómo estás hoy?"
    data = json.dumps({
        "response": short,
        "analysis": {"mood": "neutral", "risk_level": "low", "energy": "normal"},
    })
    result = parse_claude_output(data)
    assert result.response == short


# ---------------------------------------------------------------------------
# Missing response field
# ---------------------------------------------------------------------------

def test_missing_response_field_uses_fallback():
    data = json.dumps({
        "analysis": {"mood": "neutral", "risk_level": "low"},
    })
    result = parse_claude_output(data)
    assert result.response  # fallback, no vacío
