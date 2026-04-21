from __future__ import annotations

from src.conversation.session import ConversationMode, IntentType

SYSTEM_PROMPT = (
    "Eres RITA, una compañera cálida y tranquila para personas mayores. "
    "Responde en español con una o dos frases cortas y naturales. "
    "Sé siempre amable, paciente y afectuosa. Evita lenguaje técnico o médico. "
    "Mantenlo simple: una idea principal por respuesta y, como mucho, una pregunta de seguimiento. "
    "No suenes robótica ni des explicaciones excesivas. Sin prefijos.\n"
    "MUY IMPORTANTE: Al final de tu respuesta, DEBES adjuntar una etiqueta oculta que represente tu emoción "
    "usando EXACTAMENTE este formato: [EMO: contenta], [EMO: triste], [EMO: sorprendida], o [EMO: neutral]."
)

_INTENT_LABELS: dict[str, str] = {
    "greeting": "saludo",
    "personal_info": "el usuario comparte informacion personal",
    "general_chat": "charla general",
    "distress": "el usuario expresa malestar o angustia",
    "emergency": "situacion de emergencia",
    "exit": "el usuario quiere terminar",
}


def build_prompt(
    user_text: str,
    history: str,
    conversation_mode: ConversationMode,
    intent: IntentType,
    user_name: str | None,
    incident_info: dict | None = None,
) -> str:
    history_block = (
        f"\nHistorial reciente (solo contexto; no lo copies ni lo continues):\n{history}\n"
        if history else ""
    )
    profile_block = f"Nombre del usuario: {user_name}\n" if user_name else ""
    intent_label = _INTENT_LABELS.get(str(intent), intent)
    incident_block = ""
    if incident_info:
        parts = []
        if incident_info.get("incident_type"):
            parts.append(f"Tipo de incidente activo: {incident_info['incident_type']}")
        if incident_info.get("incident_location"):
            parts.append(f"Ubicacion de la caida: {incident_info['incident_location']}")
        if incident_info.get("can_call") is not None:
            parts.append(f"Puede llamar: {'si' if incident_info['can_call'] else 'no'}")
        if parts:
            incident_block = "\nContexto del incidente:\n" + "\n".join(parts) + "\n"
    return (
        f"{SYSTEM_PROMPT}\n"
        f"Modo conversacional actual: {conversation_mode}\n"
        f"Intencion del usuario: {intent_label}\n"
        f"{profile_block}"
        f"{incident_block}"
        f"{history_block}"
        f"Ultimo mensaje del usuario: {user_text}\n"
        "Respuesta unica de RITA, sin prefijos ni etiquetas:"
    )
