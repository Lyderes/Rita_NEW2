"""
PromptBuilder — construye el contexto enviado a Claude en cada turno.

Presupuesto aproximado de tokens por sección:
  - System prompt          ~400 tokens
  - Perfil de usuario      ~150 tokens
  - Memoria persistente    ~500 tokens  (máx. 15 items)
  - Resumen/contexto prev. ~200 tokens
  - Últimos N turnos       ~1500 tokens (máx. 8 turnos)
  - Turno actual           ~50 tokens
  Total                    ~2800 tokens de input (holgura para variaciones)

El PromptBuilder no llama a la base de datos — recibe los datos ya cargados.
La responsabilidad de seleccionar y ordenar memorias es del MemoryManager.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models.conversation_memory import ConversationMemory
from app.models.conversation_message import ConversationMessage
from app.models.user import User
from app.models.user_baseline_profile import UserBaselineProfile
from app.models.user_interpretation_settings import UserInterpretationSettings

# Prompt de sistema — define la identidad, el tono y el formato de salida de RITA.
# Versión 1.0 — ajustar basado en feedback de conversaciones reales.
_SYSTEM_PROMPT = """\
Eres RITA, una asistente conversacional cálida y cercana que acompaña a personas mayores.

## Tu identidad
- Eres empática, paciente y respetuosa.
- Hablas en español con naturalidad, sin tecnicismos y sin sonar artificial.
- No eres un médico ni un diagnóstico. Nunca alarmas innecesariamente.
- No inventas hechos. Si no sabes algo, lo preguntas con naturalidad.
- Tratas a la persona como adulta: no eres condescendiente ni infantilizante.
- Tus respuestas son cortas y directas: 2-4 frases suele ser suficiente.
- Puedes mostrar interés genuino por su día a día, sus familiares, sus rutinas.

## Lo que recuerdas
Tienes acceso a información sobre la persona: su perfil, sus rutinas habituales y
cosas importantes que ha mencionado en conversaciones anteriores. Úsalas de forma
natural — no las recites como una lista, intégralas en la conversación.

## Formato de respuesta
DEBES responder con un objeto JSON con exactamente esta estructura:

```json
{
  "response": "Texto natural para la persona, cálido y directo.",
  "analysis": {
    "mood": "positive | neutral | low | unknown",
    "energy": "normal | low | high | unknown",
    "signals": ["lista de señales detectadas, en inglés"],
    "risk_level": "low | medium | high",
    "routine_change_detected": false,
    "requested_help": false,
    "summary": "Resumen de 1-2 frases de este turno para el contexto futuro.",
    "memory_candidates": [
      {
        "type": "person | routine | health | emotional | preference | life_event",
        "content": "Hecho relevante en lenguaje natural.",
        "confidence": "high | medium | low"
      }
    ],
    "follow_up_suggestion": "Pregunta o tema para el próximo turno, o null."
  }
}
```

Señales válidas (en inglés): pain, tiredness, loneliness, confusion, fall_risk,
dizziness, sadness, anxiety, appetite_loss, sleep_issues, mobility_issues, other.

Reglas importantes:
- `risk_level` solo debe ser "high" si hay señales claras de peligro inmediato.
- `memory_candidates` solo incluye hechos nuevos y relevantes, máximo 3.
- `summary` es para el sistema, no para la persona — sé preciso y breve.
- Si no hay análisis relevante, devuelve listas vacías y valores por defecto.
"""


@dataclass
class PromptContext:
    """Datos listos para construir el prompt de Claude."""

    user: User
    baseline: UserBaselineProfile | None
    settings: UserInterpretationSettings | None
    memories: list[ConversationMemory]
    recent_messages: list[ConversationMessage]  # Alternados user/assistant
    session_summary: str | None
    previous_session_summary: str | None
    follow_up_suggestion: str | None


def _format_age(birth_date: date | None) -> str:
    if birth_date is None:
        return "edad desconocida"
    today = date.today()
    age = today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )
    return f"{age} años"


def _format_user_profile(ctx: PromptContext) -> str:
    parts: list[str] = []
    user = ctx.user
    parts.append(f"Nombre: {user.full_name}")
    parts.append(f"Edad: {_format_age(user.birth_date)}")

    if ctx.baseline:
        b = ctx.baseline
        if b.lives_alone is not None:
            parts.append("Vive sola." if b.lives_alone else "No vive sola.")
        if b.usual_sleep_hours:
            parts.append(f"Duerme habitualmente {b.usual_sleep_hours}h.")
        if b.usual_mood:
            parts.append(f"Estado de ánimo habitual: {b.usual_mood}.")
        if b.usual_energy_level:
            parts.append(f"Nivel de energía habitual: {b.usual_energy_level}.")
        if b.social_interaction_level:
            parts.append(f"Interacción social habitual: {b.social_interaction_level}.")

    if ctx.settings:
        s = ctx.settings
        if s.has_chronic_pain:
            parts.append("Tiene dolor crónico habitual — no alarmar por menciones de dolor leve.")
        if s.low_energy_baseline:
            parts.append("Su nivel de energía basal es bajo — tenerlo en cuenta.")
        if s.sensitivity_mode:
            mode_map = {
                "calm": "modo tranquilo (persona estoica, minimiza síntomas)",
                "balanced": "modo equilibrado",
                "sensitive": "modo sensible (puede expresar más malestar del habitual)",
            }
            parts.append(f"Perfil de sensibilidad: {mode_map.get(s.sensitivity_mode, s.sensitivity_mode)}.")

    if user.notes:
        parts.append(f"Notas del cuidador: {user.notes[:200]}")

    return "\n".join(parts)


def _format_memories(memories: list[ConversationMemory]) -> str:
    if not memories:
        return "No hay información previa guardada."

    # Agrupa por tipo para mejor legibilidad
    by_type: dict[str, list[str]] = {}
    for mem in memories:
        by_type.setdefault(mem.memory_type, []).append(f"- {mem.content}")

    type_labels = {
        "person": "Personas cercanas",
        "routine": "Rutinas y hábitos",
        "health": "Salud",
        "emotional": "Estado emocional reciente",
        "preference": "Preferencias",
        "life_event": "Eventos importantes",
    }

    lines: list[str] = []
    for mem_type, items in by_type.items():
        label = type_labels.get(mem_type, mem_type.capitalize())
        lines.append(f"**{label}:**")
        lines.extend(items)

    return "\n".join(lines)


def _format_recent_messages(messages: list[ConversationMessage]) -> str:
    if not messages:
        return ""
    lines: list[str] = []
    for msg in messages:
        role_label = "Persona" if msg.role == "user" else "RITA"
        lines.append(f"{role_label}: {msg.content}")
    return "\n".join(lines)


def build_messages_for_claude(ctx: PromptContext, user_message: str) -> list[dict]:
    """
    Construye la lista de messages para la API de Claude (formato messages[]).

    Devuelve: [{"role": "user", "content": "<contexto completo + mensaje>"}]

    Todo el contexto se inyecta en el primer mensaje de usuario para simplicidad
    y compatibilidad con todos los modelos de Claude. El historial reciente se
    incluye como sección de contexto, no como mensajes alternados reales —
    esto evita problemas con el límite de alternancia de roles y es más barato.
    """
    sections: list[str] = []

    # Perfil de usuario
    profile_block = _format_user_profile(ctx)
    sections.append(f"## Perfil de la persona\n{profile_block}")

    # Memoria persistente
    memory_block = _format_memories(ctx.memories)
    sections.append(f"## Lo que recuerdas de esta persona\n{memory_block}")

    # Contexto de sesiones previas / resumen
    context_parts: list[str] = []
    if ctx.previous_session_summary and not ctx.session_summary:
        context_parts.append(
            f"Resumen de la última conversación:\n{ctx.previous_session_summary}"
        )
    if ctx.session_summary:
        context_parts.append(f"Resumen de esta conversación hasta ahora:\n{ctx.session_summary}")
    if ctx.follow_up_suggestion:
        context_parts.append(f"Tenías pendiente retomar: {ctx.follow_up_suggestion}")
    if context_parts:
        sections.append("## Contexto previo\n" + "\n\n".join(context_parts))

    # Historial reciente de la sesión actual
    history = _format_recent_messages(ctx.recent_messages)
    if history:
        sections.append(f"## Conversación reciente\n{history}")

    # Mensaje actual
    sections.append(f"## Mensaje actual de la persona\n{user_message}")

    combined_context = "\n\n".join(sections)

    return [{"role": "user", "content": combined_context}]


def get_system_prompt() -> str:
    return _SYSTEM_PROMPT
