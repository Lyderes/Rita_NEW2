"""
Parser y validador de la salida estructurada de Claude para el sistema conversacional.

Responsabilidad única: transformar el texto raw de Claude en un
ClaudeConversationOutput validado o, si falla, en un objeto de fallback seguro.

El backend NUNCA confía ciegamente en la salida del modelo:
  1. Se extrae el JSON del texto (puede venir envuelto en ```json ... ```)
  2. Se valida con Pydantic
  3. Si falla: se conserva la respuesta de texto y se descarta el análisis
  4. Se sanean valores fuera de rango
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.schemas.conversation import ClaudeConversationOutput, TurnAnalysis

logger = logging.getLogger(__name__)

# Valores permitidos — el parser rechaza cualquier valor fuera de estos conjuntos.
_VALID_MOODS = {"positive", "neutral", "low", "unknown"}
_VALID_ENERGY = {"normal", "low", "high", "unknown"}
_VALID_RISK = {"low", "medium", "high"}
_VALID_MEMORY_TYPES = {"person", "routine", "health", "emotional", "preference", "life_event"}
_VALID_CONFIDENCE = {"high", "medium", "low"}

# Máximo de caracteres permitidos en la respuesta conversacional
_MAX_RESPONSE_LENGTH = 800

# Fallback cuando Claude no responde o falla la validación
_FALLBACK_RESPONSE = (
    "Disculpa, no he podido entenderte bien. ¿Puedes repetirlo?"
)


def _extract_json_block(text: str) -> str | None:
    """Extrae el contenido JSON del texto, limpiando bloques de código si los hay."""
    # Intenta extraer ```json ... ``` o ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)

    # Si no hay bloque de código, busca el primer objeto JSON en el texto
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)

    return None


def _sanitize_analysis(data: dict[str, Any]) -> dict[str, Any]:
    """Normaliza valores fuera de rango a sus defaults seguros."""
    if data.get("mood") not in _VALID_MOODS:
        data["mood"] = "unknown"
    if data.get("energy") not in _VALID_ENERGY:
        data["energy"] = "unknown"
    if data.get("risk_level") not in _VALID_RISK:
        data["risk_level"] = "low"

    # Limpiar memory_candidates inválidos
    cleaned_candidates = []
    for candidate in data.get("memory_candidates", []):
        if not isinstance(candidate, dict):
            continue
        if candidate.get("type") not in _VALID_MEMORY_TYPES:
            continue
        if not candidate.get("content", "").strip():
            continue
        if candidate.get("confidence") not in _VALID_CONFIDENCE:
            candidate["confidence"] = "medium"
        # Truncar contenido largo
        candidate["content"] = candidate["content"][:500]
        cleaned_candidates.append(candidate)
    data["memory_candidates"] = cleaned_candidates[:5]  # Máximo 5

    return data


def _truncate_response(text: str) -> str:
    """Trunca respuestas excesivamente largas manteniendo oraciones completas."""
    if len(text) <= _MAX_RESPONSE_LENGTH:
        return text
    truncated = text[:_MAX_RESPONSE_LENGTH]
    # Cortar en el último punto para no dejar frases a medias
    last_period = max(truncated.rfind("."), truncated.rfind("?"), truncated.rfind("!"))
    if last_period > _MAX_RESPONSE_LENGTH // 2:
        truncated = truncated[: last_period + 1]
    logger.warning("Claude response truncated from %d to %d chars", len(text), len(truncated))
    return truncated


def parse_claude_output(raw_text: str) -> ClaudeConversationOutput:
    """
    Parsea y valida la respuesta de Claude.

    Returns:
        ClaudeConversationOutput validado. Nunca lanza excepción —
        en caso de error devuelve un objeto de fallback seguro.
    """
    if not raw_text or not raw_text.strip():
        logger.warning("Claude returned empty response")
        return ClaudeConversationOutput(
            response=_FALLBACK_RESPONSE,
            analysis=TurnAnalysis(),
        )

    json_block = _extract_json_block(raw_text)
    if json_block is None:
        # Claude respondió en texto plano sin JSON — usamos el texto tal cual
        logger.info("Claude returned plain text without JSON block — using as response")
        return ClaudeConversationOutput(
            response=_truncate_response(raw_text.strip()),
            analysis=TurnAnalysis(),
        )

    try:
        raw_json = json.loads(json_block)
    except json.JSONDecodeError as exc:
        logger.warning("JSON decode error in Claude output: %s | raw=%s", exc, json_block[:200])
        return ClaudeConversationOutput(
            response=_truncate_response(raw_text.strip()),
            analysis=TurnAnalysis(),
        )

    if not isinstance(raw_json, dict):
        logger.warning("Claude JSON is not a dict: %s", type(raw_json))
        return ClaudeConversationOutput(
            response=_FALLBACK_RESPONSE,
            analysis=TurnAnalysis(),
        )

    # Extraer el campo 'response'
    response_text = raw_json.get("response", "")
    if not response_text or not str(response_text).strip():
        # Si no hay campo response intenta usarlo todo como respuesta
        response_text = _FALLBACK_RESPONSE
        logger.warning("Claude JSON missing 'response' field")
    else:
        response_text = _truncate_response(str(response_text).strip())

    # Extraer y validar el bloque 'analysis'
    analysis_data = raw_json.get("analysis", {})
    if not isinstance(analysis_data, dict):
        analysis_data = {}

    analysis_data = _sanitize_analysis(analysis_data)

    try:
        analysis = TurnAnalysis(**analysis_data)
    except ValidationError as exc:
        logger.warning("TurnAnalysis validation failed: %s", exc)
        analysis = TurnAnalysis()

    return ClaudeConversationOutput(response=response_text, analysis=analysis)
