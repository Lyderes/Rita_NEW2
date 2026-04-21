"""
Schemas Pydantic para el sistema conversacional de RITA.

Contrato de entrada/salida entre la API, el ConversationService y Claude.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Contrato de salida estructurada de Claude (TurnAnalysis)
# ---------------------------------------------------------------------------

class MemoryCandidate(BaseModel):
    """Un hecho que Claude propone guardar en memoria persistente."""

    type: str = Field(
        description="Tipo de memoria: person | routine | health | emotional | preference | life_event"
    )
    content: str = Field(
        description="Hecho en lenguaje natural. Ej: 'Tiene una hija llamada Ana en Madrid.'",
        max_length=500,
    )
    confidence: str = Field(
        description="Confianza en la relevancia: high | medium | low",
        default="medium",
    )


class TurnAnalysis(BaseModel):
    """
    Análisis estructurado que Claude devuelve junto con la respuesta conversacional.

    El backend valida este objeto con Pydantic. Si la validación falla, se descarta
    el análisis pero se conserva la respuesta de texto.
    """

    mood: str = Field(
        default="unknown",
        description="Estado de ánimo detectado: positive | neutral | low | unknown",
    )
    energy: str = Field(
        default="unknown",
        description="Nivel de energía: normal | low | high | unknown",
    )
    signals: list[str] = Field(
        default_factory=list,
        description="Señales detectadas: pain, tiredness, loneliness, confusion, fall_risk, ...",
    )
    risk_level: str = Field(
        default="low",
        description="Nivel de riesgo PROPUESTO por Claude: low | medium | high. "
                    "El backend aplica sus propias reglas antes de actuar.",
    )
    routine_change_detected: bool = Field(
        default=False,
        description="True si el usuario menciona un cambio en su rutina habitual.",
    )
    requested_help: bool = Field(
        default=False,
        description="True si el usuario ha pedido ayuda explícitamente.",
    )
    summary: str = Field(
        default="",
        description="Resumen de 1-2 frases de este turno para alimentar el contexto futuro.",
        max_length=300,
    )
    memory_candidates: list[MemoryCandidate] = Field(
        default_factory=list,
        description="Hechos que Claude propone guardar en memoria persistente.",
        max_length=5,  # Claude no puede proponer más de 5 por turno
    )
    follow_up_suggestion: str | None = Field(
        default=None,
        description="Pregunta o tema para retomar en el próximo turno.",
        max_length=200,
    )


class ClaudeConversationOutput(BaseModel):
    """
    Respuesta completa de Claude para un turno conversacional.

    Claude devuelve un JSON con esta estructura. Si el campo 'analysis' falla
    la validación, se usa sólo 'response'.
    """

    response: str = Field(
        description="Texto natural para la persona usuaria. Cálido, claro, sin tecnicismos."
    )
    analysis: TurnAnalysis = Field(
        default_factory=TurnAnalysis,
        description="Análisis estructurado del turno.",
    )


# ---------------------------------------------------------------------------
# Schemas de API (entrada)
# ---------------------------------------------------------------------------

class ConversationStartRequest(BaseModel):
    """Crea o reanuda la sesión activa de un usuario."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"force_new": False}}
    )

    force_new: bool = Field(
        default=False,
        description="Si True, cierra la sesión activa actual y crea una nueva.",
    )


class ConversationTurnRequest(BaseModel):
    """Mensaje del usuario en una sesión activa."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"message": "Hola RITA, hoy me siento un poco cansada."}}
    )

    message: str = Field(
        min_length=1,
        max_length=2000,
        description="Mensaje de la persona usuaria.",
    )


# ---------------------------------------------------------------------------
# Schemas de API (respuesta)
# ---------------------------------------------------------------------------

class ConversationSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: str
    turn_count: int
    session_summary: str | None
    follow_up_suggestion: str | None
    started_at: datetime
    last_activity_at: datetime
    ended_at: datetime | None


class ConversationMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    content: str
    turn_index: int
    mood: str | None
    risk_level: str | None
    requested_help: bool | None
    routine_change_detected: bool | None
    created_at: datetime


class ConversationTurnResponse(BaseModel):
    """Respuesta al endpoint POST /conversations/{session_id}/turns."""

    session_id: int
    turn_index: int
    response: str = Field(description="Texto de RITA para mostrar al usuario.")
    # Campos de análisis normalizados (útiles para el cliente si quiere mostrarlos)
    mood: str | None = None
    risk_level: str | None = None
    requested_help: bool = False
    # True si el backend decidió actuar (crear evento/alerta), no solo Claude
    backend_action_taken: bool = False


class ConversationMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    memory_type: str
    content: str
    confidence: str
    mention_count: int
    is_active: bool
    first_mentioned_at: datetime
    last_confirmed_at: datetime
