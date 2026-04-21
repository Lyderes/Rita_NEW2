from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.enums import EventTypeEnum, SeverityEnum


TextPolicy = Literal["required", "optional", "irrelevant"]


# Recommended external input event types for edge and future integrations.
CANONICAL_INPUT_EVENT_TYPES = frozenset(
    {
        EventTypeEnum.device_offline,
        EventTypeEnum.help_request,
        EventTypeEnum.pain_report,
        EventTypeEnum.fall_suspected,
        EventTypeEnum.emergency_keyword_detected,
        EventTypeEnum.conversation_anomaly,
        EventTypeEnum.wellbeing_check_failed,
    }
)

# Accepted only for backward compatibility; avoid for new integrations.
LEGACY_INPUT_EVENT_TYPES = frozenset(
    {
        EventTypeEnum.fall,
        EventTypeEnum.emergency,
        EventTypeEnum.distress,
        EventTypeEnum.checkin,
        EventTypeEnum.user_speech,
        EventTypeEnum.assistant_response,
    }
)

# Internal domain types derived for incidents/alerts, never valid as external input.
DERIVED_INTERNAL_EVENT_TYPES = frozenset(
    {
        EventTypeEnum.device_connectivity,
        EventTypeEnum.assistance_needed,
        EventTypeEnum.health_concern,
        EventTypeEnum.possible_fall,
        EventTypeEnum.emergency_risk,
        EventTypeEnum.wellbeing_failure,
        EventTypeEnum.reminder_triggered,
        EventTypeEnum.reminder_confirmed,
    }
)


@dataclass(frozen=True)
class EventRule:
    severity: SeverityEnum
    allowed_severities: frozenset[SeverityEnum]
    text_policy: TextPolicy
    payload_required_all: frozenset[str]
    payload_required_any: frozenset[str]
    payload_forbidden: frozenset[str]
    requires_user_text_or_payload_any: frozenset[str]
    opens_incident: bool
    incident_type: EventTypeEnum | None
    creates_alert: bool
    dedup_minutes: int | None

    @property
    def is_stateful(self) -> bool:
        return self.opens_incident or self.creates_alert


EVENT_RULES: dict[EventTypeEnum, EventRule] = {
    EventTypeEnum.device_offline: EventRule(
        severity=SeverityEnum.high,
        allowed_severities=frozenset({SeverityEnum.high}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset(),
        opens_incident=True,
        incident_type=EventTypeEnum.device_connectivity,
        creates_alert=True,
        dedup_minutes=30,
    ),
    EventTypeEnum.help_request: EventRule(
        severity=SeverityEnum.high,
        allowed_severities=frozenset({SeverityEnum.high}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset({"reason"}),
        opens_incident=True,
        incident_type=EventTypeEnum.assistance_needed,
        creates_alert=True,
        dedup_minutes=None,
    ),
    EventTypeEnum.pain_report: EventRule(
        severity=SeverityEnum.medium,
        allowed_severities=frozenset({SeverityEnum.medium}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset({"pain_level"}),
        opens_incident=True,
        incident_type=EventTypeEnum.health_concern,
        creates_alert=True,
        dedup_minutes=10,
    ),
    EventTypeEnum.fall_suspected: EventRule(
        severity=SeverityEnum.critical,
        allowed_severities=frozenset({SeverityEnum.critical}),
        text_policy="optional",
        payload_required_all=frozenset({"confidence"}),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset(),
        opens_incident=True,
        incident_type=EventTypeEnum.possible_fall,
        creates_alert=True,
        dedup_minutes=None,
    ),
    EventTypeEnum.emergency_keyword_detected: EventRule(
        severity=SeverityEnum.critical,
        allowed_severities=frozenset({SeverityEnum.critical}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset({"keyword"}),
        opens_incident=True,
        incident_type=EventTypeEnum.emergency_risk,
        creates_alert=True,
        dedup_minutes=None,
    ),
    EventTypeEnum.conversation_anomaly: EventRule(
        severity=SeverityEnum.low,
        allowed_severities=frozenset({SeverityEnum.low}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset(),
        opens_incident=False,
        incident_type=None,
        creates_alert=False,
        dedup_minutes=30,
    ),
    EventTypeEnum.wellbeing_check_failed: EventRule(
        severity=SeverityEnum.medium,
        allowed_severities=frozenset({SeverityEnum.medium}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset(),
        opens_incident=True,
        incident_type=EventTypeEnum.wellbeing_failure,
        creates_alert=True,
        dedup_minutes=15,
    ),
    # Legacy input event rules: accepted for compatibility, not recommended for new integrations.
    EventTypeEnum.fall: EventRule(
        severity=SeverityEnum.high,
        allowed_severities=frozenset({SeverityEnum.medium, SeverityEnum.high, SeverityEnum.critical}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset(),
        opens_incident=True,
        incident_type=EventTypeEnum.fall,
        creates_alert=True,
        dedup_minutes=5,
    ),
    EventTypeEnum.emergency: EventRule(
        severity=SeverityEnum.high,
        allowed_severities=frozenset({SeverityEnum.high, SeverityEnum.critical}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset(),
        opens_incident=True,
        incident_type=EventTypeEnum.emergency,
        creates_alert=True,
        dedup_minutes=5,
    ),
    EventTypeEnum.distress: EventRule(
        severity=SeverityEnum.medium,
        allowed_severities=frozenset({SeverityEnum.medium, SeverityEnum.high}),
        text_policy="required",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset(),
        opens_incident=False,
        incident_type=None,
        creates_alert=False,
        dedup_minutes=None,
    ),
    EventTypeEnum.checkin: EventRule(
        severity=SeverityEnum.low,
        allowed_severities=frozenset({SeverityEnum.low}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset(),
        opens_incident=False,
        incident_type=None,
        creates_alert=False,
        dedup_minutes=None,
    ),
    EventTypeEnum.user_speech: EventRule(
        severity=SeverityEnum.low,
        allowed_severities=frozenset({SeverityEnum.low}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset(),
        opens_incident=False,
        incident_type=None,
        creates_alert=False,
        dedup_minutes=None,
    ),
    EventTypeEnum.assistant_response: EventRule(
        severity=SeverityEnum.low,
        allowed_severities=frozenset({SeverityEnum.low}),
        text_policy="optional",
        payload_required_all=frozenset(),
        payload_required_any=frozenset(),
        payload_forbidden=frozenset(),
        requires_user_text_or_payload_any=frozenset(),
        opens_incident=False,
        incident_type=None,
        creates_alert=False,
        dedup_minutes=None,
    ),
}


_ALL_CLASSIFIED_EVENT_TYPES = (
    CANONICAL_INPUT_EVENT_TYPES | LEGACY_INPUT_EVENT_TYPES | DERIVED_INTERNAL_EVENT_TYPES
)
assert not (CANONICAL_INPUT_EVENT_TYPES & LEGACY_INPUT_EVENT_TYPES)
assert not (CANONICAL_INPUT_EVENT_TYPES & DERIVED_INTERNAL_EVENT_TYPES)
assert not (LEGACY_INPUT_EVENT_TYPES & DERIVED_INTERNAL_EVENT_TYPES)
assert _ALL_CLASSIFIED_EVENT_TYPES == frozenset(EventTypeEnum)


def get_input_event_rule(event_type: EventTypeEnum) -> EventRule | None:
    return EVENT_RULES.get(event_type)


def is_supported_input_event_type(event_type: EventTypeEnum) -> bool:
    return event_type in CANONICAL_INPUT_EVENT_TYPES or event_type in LEGACY_INPUT_EVENT_TYPES


def is_derived_internal_event_type(event_type: EventTypeEnum) -> bool:
    return event_type in DERIVED_INTERNAL_EVENT_TYPES
