from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import re
from typing import Literal

ConversationMode = Literal["normal", "supportive", "risk_alert"]
IntentType = Literal[
    "greeting",
    "personal_info",
    "general_chat",
    "distress",
    "emergency",
    "exit",
]

_EXIT_WORDS = {"salir", "adios", "adios.", "adios!", "terminar", "hasta luego"}
_GREETING_PATTERNS = (
    r"\bhola\b",
    r"\bbuen[oa]s?\s+d[ií]as\b",
    r"\bbuen[oa]s?\s+tardes\b",
    r"\bbuen[oa]s?\s+noches\b",
)
_DISTRESS_PATTERNS = (
    r"\bmuy\s+mal\b",
    r"\bme\s+siento\s+(?:mal|mareado|cansado|solo|deprimido)\b",
    r"\bme\s+encuentro\s+(?:mal|mareado|cansado|solo|deprimido)\b",
    r"\bestoy\s+(?:mal|mareado|cansado|solo|deprimido|angustiado)\b",
    r"\btriste\b",
    r"\bansios[oa]\b",
    r"\bmareado\b",
    r"\bdolor\b",
    r"\bno\s+me\s+(?:encuentro|siento)\s+bien\b",
)
_EMERGENCY_PATTERNS = (
    r"\bme\s+he\s+ca[ií]do\b",
    r"\bayuda\b",
    r"\bsocorro\b",
    r"\bllama\s+a\s+alguien\b",
    r"\b112\b",
)
_NAME_PATTERNS = (
    re.compile(r"\bme\s+llamo\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ]{2,})", re.IGNORECASE),
    re.compile(r"\bsoy\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ]{2,})", re.IGNORECASE),
)

# ---------- Fall-incident constants ----------

_FALL_TRIGGER = re.compile(
    r"\bme\s+(?:he\s+)?ca[ií]d[oa]\b|\bme\s+ca[ií]\b",
    re.IGNORECASE,
)

_LOCATION_STOP_WORDS = frozenset({
    "cabeza", "rodilla", "pierna", "brazo", "espalda", "cuello",
    "tobillo", "codo", "cadera", "pie", "mano", "hombro",
    "momento", "descuido", "instante",
})
_LOCATION_PATTERN = re.compile(
    r"\ben\s+(?:la\s+|el\s+|mi\s+|una?\s+)?([a-zA-ZáéíóúÁÉÍÓÚñÑ]{3,})\b",
    re.IGNORECASE,
)

_NO_CALL_PATTERNS = (
    re.compile(r"no\s+puedo\s+llamar", re.IGNORECASE),
    re.compile(r"no\s+tengo\s+(?:el\s+)?(?:tel[eé]fono|m[oó]vil|celular)", re.IGNORECASE),
    re.compile(r"no\s+alcanzo\s+(?:el\s+)?(?:tel[eé]fono|m[oó]vil)", re.IGNORECASE),
    re.compile(r"no\s+llego\s+(?:al?\s+)?(?:tel[eé]fono|m[oó]vil)", re.IGNORECASE),
)
_CAN_CALL_PATTERNS = (
    re.compile(r"(?:s[ií]|tengo|puedo)\s+(?:el\s+)?(?:tel[eé]fono|m[oó]vil|celular)", re.IGNORECASE),
    re.compile(r"puedo\s+llamar", re.IGNORECASE),
)

_FALL_PROTOCOL = (
    "¿Puedes hablar con claridad y moverte, o estás atascado?",
    "¿Te has golpeado la cabeza o el cuello?",
    "¿Tienes dolor fuerte en alguna zona o ves sangre?",
    "¿Tienes el teléfono cerca o puedes alcanzarlo?",
    "¿Hay alguien cerca que pueda escucharte o ayudarte?",
    "¿En qué habitación o zona ocurrió la caída?",
)


@dataclass(slots=True)
class ChatTurn:
    role: str
    content: str


class ConversationSession:
    """Short-term memory plus lightweight conversational state."""

    def __init__(self, max_turns: int = 8) -> None:
        self._turns: deque[ChatTurn] = deque(maxlen=max_turns)
        self.conversation_mode: ConversationMode = "normal"
        self.last_intent: IntentType = "general_chat"
        self.user_name: str | None = None
        # Incident tracking
        self.incident_type: str | None = None
        self.incident_location: str | None = None
        self.can_call: bool | None = None
        self.emergency_step: int = 0
        # Follow-up context: topic of the last local response ("pain"/"sleep"/"unwell")
        self.last_local_topic: str | None = None

    def infer_intent(self, text: str) -> IntentType:
        normalized = text.strip().lower()
        if not normalized:
            return "general_chat"

        if normalized in _EXIT_WORDS:
            return "exit"

        if self.extract_name(text) is not None:
            return "personal_info"

        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _EMERGENCY_PATTERNS):
            return "emergency"

        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _DISTRESS_PATTERNS):
            return "distress"

        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _GREETING_PATTERNS):
            return "greeting"

        return "general_chat"

    def extract_name(self, text: str) -> str | None:
        for pattern in _NAME_PATTERNS:
            match = pattern.search(text.strip())
            if match:
                candidate = match.group(1).strip()
                return candidate[:1].upper() + candidate[1:].lower()
        return None

    def update_state(self, user_text: str, risk_detected: bool) -> IntentType:
        intent = self.infer_intent(user_text)
        self.last_intent = intent

        maybe_name = self.extract_name(user_text)
        if maybe_name:
            self.user_name = maybe_name

        if risk_detected or intent == "emergency":
            self.conversation_mode = "risk_alert"
            return intent

        if intent == "distress":
            self.conversation_mode = "supportive"
            return intent

        # De-escalate only when no fall protocol is active
        if (
            not self.fall_incident_is_active()
            and self.conversation_mode == "risk_alert"
            and intent in {"personal_info", "greeting", "general_chat"}
        ):
            self.conversation_mode = "supportive"
            return intent

        if self.conversation_mode == "supportive" and intent in {"personal_info", "greeting", "general_chat"}:
            self.conversation_mode = "normal"

        return intent

    def add_user(self, text: str) -> None:
        self._turns.append(ChatTurn(role="usuario", content=text.strip()))

    def add_assistant(self, text: str) -> None:
        self._turns.append(ChatTurn(role="rita", content=text.strip()))

    def history_text(self, last_turns: int = 3, max_chars: int = 300) -> str:
        if not self._turns:
            return ""
        window = list(self._turns)[-last_turns:] if last_turns > 0 else list(self._turns)
        lines = [f"{turn.role}: {turn.content}" for turn in window]
        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[-max_chars:]
        return text

    # ---------- Fall-protocol helpers ----------

    def is_fall_trigger(self, text: str) -> bool:
        return bool(_FALL_TRIGGER.search(text))

    def open_fall_incident(self) -> None:
        self.incident_type = "fall"
        self.incident_location = None
        self.can_call = None
        self.emergency_step = 0
        self.last_local_topic = None
        self.conversation_mode = "risk_alert"

    def close_incident(self) -> None:
        self.incident_type = None
        self.incident_location = None
        self.can_call = None
        self.emergency_step = 0
        self.last_local_topic = None
        if self.conversation_mode == "risk_alert":
            self.conversation_mode = "supportive"
        # Avoid dragging a finished emergency protocol into the next LLM prompt.
        self._turns.clear()

    def fall_incident_is_active(self) -> bool:
        """True while the step-by-step fall protocol is still in progress."""
        return self.incident_type == "fall" and self.emergency_step <= len(_FALL_PROTOCOL)

    def extract_incident_info(self, text: str) -> None:
        """Extract and persist location and phone-availability from user text."""
        if self.incident_location is None:
            m = _LOCATION_PATTERN.search(text)
            if m:
                candidate = m.group(1).lower()
                if candidate not in _LOCATION_STOP_WORDS:
                    self.incident_location = candidate

        if self.can_call is None:
            if any(p.search(text) for p in _NO_CALL_PATTERNS):
                self.can_call = False
            elif any(p.search(text) for p in _CAN_CALL_PATTERNS):
                self.can_call = True

    def fall_protocol_next(self, user_text: str) -> str:
        """Extract info from user_text and return the next protocol response."""
        self.extract_incident_info(user_text)
        step = self.emergency_step

        if step == 0:
            self.emergency_step = 1
            loc_part = f" en {self.incident_location}" if self.incident_location else ""
            return f"Entendido, me quedo contigo{loc_part}. {_FALL_PROTOCOL[0]}"

        if step == 1:
            self.emergency_step = 2
            return _FALL_PROTOCOL[1]

        if step == 2:
            self.emergency_step = 3
            return _FALL_PROTOCOL[2]

        if step == 3:
            self.emergency_step = 4
            if self.can_call is True:
                return "Bien. Llama ahora al 112 o a un familiar de confianza. Estoy aquí contigo."
            if self.can_call is False:
                return _FALL_PROTOCOL[4]
            return _FALL_PROTOCOL[3]

        if step == 4:
            if self.can_call is None:
                if re.search(r"\bno\b", user_text, re.IGNORECASE):
                    self.can_call = False
                elif re.search(r"\bs[ií]\b", user_text, re.IGNORECASE):
                    self.can_call = True
            self.emergency_step = 5
            if self.can_call is True:
                return "Bien. Llama ahora al 112 o a un familiar de confianza. Estoy aquí contigo."
            if self.can_call is False:
                return _FALL_PROTOCOL[4]
            return "¿Puedes marcar el 112 u otro número con tu teléfono?"

        if step == 5:
            self.emergency_step = 6
            if self.incident_location:
                return f"Recuerdo que estás en {self.incident_location}. {_FALL_PROTOCOL[5]}"
            return _FALL_PROTOCOL[5]

        # step == 6: last answer received, close protocol
        loc_part = f" en {self.incident_location}" if self.incident_location else ""
        final_text = f"Gracias{loc_part}. Estoy aquí contigo. Dime si necesitas algo más."
        self.close_incident()
        return final_text
