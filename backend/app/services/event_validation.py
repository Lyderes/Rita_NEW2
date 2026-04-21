from __future__ import annotations

from numbers import Real

from app.domain.enums import EventTypeEnum, SeverityEnum
from app.domain.event_catalog import EventRule


def _normalized_text(value: str | None) -> str:
    return (value or "").strip()


def _is_real_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _validate_non_empty_payload_text(payload: dict[str, object], key: str) -> str | None:
    if key not in payload:
        return None
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        return f"invalid payload field: {key} must be a non-empty string"
    return None


def _validate_confidence(payload: dict[str, object]) -> str | None:
    if "confidence" not in payload:
        return None
    value = payload["confidence"]
    if not _is_real_number(value):
        return "invalid payload field: confidence must be numeric between 0 and 1"
    numeric_value = float(value)
    if numeric_value < 0 or numeric_value > 1:
        return "invalid payload field: confidence must be numeric between 0 and 1"
    return None


def _validate_pain_level(payload: dict[str, object]) -> str | None:
    if "pain_level" not in payload:
        return None
    value = payload["pain_level"]
    if not _is_real_number(value):
        return "invalid payload field: pain_level must be numeric between 1 and 10"
    numeric_value = float(value)
    if numeric_value < 1 or numeric_value > 10:
        return "invalid payload field: pain_level must be numeric between 1 and 10"
    return None


def _has_meaningful_payload_value(payload: dict[str, object], key: str) -> bool:
    if key not in payload:
        return False
    value = payload[key]
    if key in {"keyword", "reason"}:
        return isinstance(value, str) and bool(value.strip())
    if key == "pain_level":
        return _validate_pain_level(payload) is None
    if key == "confidence":
        return _validate_confidence(payload) is None
    return value is not None


def validate_event_semantics(
    *,
    rule: EventRule,
    event_type: EventTypeEnum,
    severity: SeverityEnum,
    user_text: str | None,
    payload_json: dict | None,
) -> str | None:
    payload = payload_json or {}
    normalized_user_text = _normalized_text(user_text)

    if severity not in rule.allowed_severities:
        allowed = ", ".join(sorted(item.value for item in rule.allowed_severities))
        return (
            f"unsupported severity for event_type '{event_type.value}': "
            f"'{severity.value}' not in [{allowed}]"
        )

    for validator in (
        _validate_confidence,
        _validate_pain_level,
        lambda current_payload: _validate_non_empty_payload_text(current_payload, "keyword"),
        lambda current_payload: _validate_non_empty_payload_text(current_payload, "reason"),
    ):
        error = validator(payload)
        if error is not None:
            return error

    if rule.text_policy == "required" and not normalized_user_text:
        return f"missing required user_text for event_type '{event_type.value}'"

    if rule.payload_required_all:
        missing = sorted(key for key in rule.payload_required_all if key not in payload)
        if missing:
            missing_str = ", ".join(missing)
            return f"missing required payload field: {missing_str}"

    if rule.payload_required_any and not any(_has_meaningful_payload_value(payload, key) for key in rule.payload_required_any):
        required_any = ", ".join(f"payload.{key}" for key in sorted(rule.payload_required_any))
        return f"missing required payload field (one of): {required_any}"

    if rule.requires_user_text_or_payload_any and not normalized_user_text:
        if not any(_has_meaningful_payload_value(payload, key) for key in rule.requires_user_text_or_payload_any):
            first_key = sorted(rule.requires_user_text_or_payload_any)[0]
            return f"{event_type.value} requires user_text or payload.{first_key}"

    if rule.payload_forbidden:
        forbidden = sorted(key for key in rule.payload_forbidden if key in payload)
        if forbidden:
            forbidden_str = ", ".join(forbidden)
            return f"forbidden payload field for event_type '{event_type.value}': {forbidden_str}"

    return None