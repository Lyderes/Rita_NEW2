from __future__ import annotations

from collections.abc import Mapping

from app.domain.enums import AlertStatusEnum, IncidentStatusEnum
from app.models.alert import Alert
from app.models.incident import Incident


class InvalidStateTransitionError(ValueError):
    """Raised when a state transition is not allowed by the domain."""


# Incident lifecycle semantics:
# - open: pending attention
# - acknowledged: being handled
# - resolved: issue solved
# - closed: administrative finalization
VALID_INCIDENT_TRANSITIONS: Mapping[IncidentStatusEnum, frozenset[IncidentStatusEnum]] = {
    IncidentStatusEnum.open: frozenset({IncidentStatusEnum.acknowledged, IncidentStatusEnum.closed}),
    IncidentStatusEnum.acknowledged: frozenset({IncidentStatusEnum.resolved, IncidentStatusEnum.closed}),
    IncidentStatusEnum.resolved: frozenset({IncidentStatusEnum.closed}),
    IncidentStatusEnum.closed: frozenset(),
}


VALID_ALERT_TRANSITIONS: Mapping[AlertStatusEnum, frozenset[AlertStatusEnum]] = {
    AlertStatusEnum.pending: frozenset({AlertStatusEnum.acknowledged, AlertStatusEnum.resolved}),
    AlertStatusEnum.acknowledged: frozenset({AlertStatusEnum.resolved}),
    AlertStatusEnum.resolved: frozenset(),
}


def _raise_invalid_transition(current: str, target: str) -> None:
    raise InvalidStateTransitionError(f"Invalid state transition: {current} → {target}")


def validate_incident_transition(
    current_status: IncidentStatusEnum,
    target_status: IncidentStatusEnum,
) -> bool:
    if current_status == target_status:
        return False
    allowed = VALID_INCIDENT_TRANSITIONS.get(current_status, frozenset())
    if target_status not in allowed:
        _raise_invalid_transition(current_status.value, target_status.value)
    return True


def validate_alert_transition(
    current_status: AlertStatusEnum,
    target_status: AlertStatusEnum,
) -> bool:
    if current_status == target_status:
        return False
    allowed = VALID_ALERT_TRANSITIONS.get(current_status, frozenset())
    if target_status not in allowed:
        _raise_invalid_transition(current_status.value, target_status.value)
    return True


def apply_incident_transition(incident: Incident, target_status: IncidentStatusEnum) -> bool:
    should_mutate = validate_incident_transition(incident.status, target_status)
    if not should_mutate:
        return False
    incident.status = target_status
    return True


def apply_alert_transition(alert: Alert, target_status: AlertStatusEnum) -> bool:
    should_mutate = validate_alert_transition(alert.status, target_status)
    if not should_mutate:
        return False
    alert.status = target_status
    return True