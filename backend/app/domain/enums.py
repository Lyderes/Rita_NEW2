from __future__ import annotations

from enum import Enum


class SeverityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EventTypeEnum(str, Enum):
    fall = "fall"
    emergency = "emergency"
    distress = "distress"
    checkin = "checkin"
    user_speech = "user_speech"
    assistant_response = "assistant_response"
    device_offline = "device_offline"
    help_request = "help_request"
    pain_report = "pain_report"
    fall_suspected = "fall_suspected"
    emergency_keyword_detected = "emergency_keyword_detected"
    conversation_anomaly = "conversation_anomaly"
    wellbeing_check_failed = "wellbeing_check_failed"
    device_connectivity = "device_connectivity"
    assistance_needed = "assistance_needed"
    health_concern = "health_concern"
    possible_fall = "possible_fall"
    emergency_risk = "emergency_risk"
    wellbeing_failure = "wellbeing_failure"
    reminder_triggered = "reminder_triggered"
    reminder_confirmed = "reminder_confirmed"


class IncidentStatusEnum(str, Enum):
    # open: incident created and pending operator attention.
    open = "open"
    # acknowledged: incident has been seen and is being handled.
    acknowledged = "acknowledged"
    # resolved: underlying issue is solved.
    resolved = "resolved"
    # closed: administrative finalization/archival after operational handling.
    closed = "closed"


class AlertStatusEnum(str, Enum):
    pending = "pending"
    acknowledged = "acknowledged"
    resolved = "resolved"


class NotificationJobStatusEnum(str, Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class NotificationChannelEnum(str, Enum):
    mock = "mock"
    mock_priority = "mock_priority"
    push = "push"
    sms = "sms"


class DeviceAdminStatusEnum(str, Enum):
    active = "active"
    suspended = "suspended"
    revoked = "revoked"
    retired = "retired"


class AuditActorTypeEnum(str, Enum):
    frontend_user = "frontend_user"
    system = "system"


class AuditTargetTypeEnum(str, Enum):
    frontend_auth = "frontend_auth"
    device = "device"


class ConversationStatusEnum(str, Enum):
    active = "active"
    ended = "ended"


class ConversationRoleEnum(str, Enum):
    user = "user"
    assistant = "assistant"


class MemoryTypeEnum(str, Enum):
    person = "person"           # Familiares, amigos, cuidadores
    routine = "routine"         # Hábitos y rutinas diarias
    health = "health"           # Estado de salud, síntomas recurrentes
    emotional = "emotional"     # Estado anímico frecuente o cambios
    preference = "preference"   # Gustos, aficiones, preferencias
    life_event = "life_event"   # Eventos relevantes de su vida


class MemoryConfidenceEnum(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ConversationMoodEnum(str, Enum):
    positive = "positive"
    neutral = "neutral"
    low = "low"
    unknown = "unknown"


class ConversationRiskEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]
