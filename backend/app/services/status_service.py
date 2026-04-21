from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum, SeverityEnum
from app.models.alert import Alert
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User
from app.schemas.status import OpenIncidentStatus, UserStatusRead

SCORE_MIN = 0
SCORE_MAX = 100

# Dominant ranges for active severe alerts (MVP hierarchical rules).
CRITICAL_ALERT_SCORE_RANGE = (0, 25)
WARNING_ALERT_SCORE_RANGE = (40, 70)

STATE_STABLE_MIN = 80
STATE_ATTENTION_MIN = 50

# Operationally active alerts for wellbeing risk.
# `acknowledged` is still unresolved (being handled), so it must keep affecting risk.
ACTIVE_ALERT_STATUSES = frozenset({AlertStatusEnum.pending, AlertStatusEnum.acknowledged})


def _clamp_score(value: int) -> int:
    return max(SCORE_MIN, min(SCORE_MAX, value))


def _is_active_alert(alert: Alert) -> bool:
    return alert.status in ACTIVE_ALERT_STATUSES


def has_critical_alerts(alerts: list[Alert]) -> bool:
    return any(_is_active_alert(alert) and alert.severity == SeverityEnum.critical for alert in alerts)


def has_warning_alerts(alerts: list[Alert]) -> bool:
    return any(
        _is_active_alert(alert) and alert.severity in {SeverityEnum.high, SeverityEnum.medium}
        for alert in alerts
    )


def score_to_state(score: int) -> str:
    if score >= STATE_STABLE_MIN:
        return "estable"
    if score >= STATE_ATTENTION_MIN:
        return "atencion"
    return "critico"


def _range_score_by_count(min_value: int, max_value: int, item_count: int, step: int) -> int:
    bounded_count = max(1, item_count)
    return max(min_value, max_value - (bounded_count - 1) * step)


def _score_from_critical_alerts(alerts: list[Alert]) -> int:
    critical_count = sum(
        1 for alert in alerts if _is_active_alert(alert) and alert.severity == SeverityEnum.critical
    )
    return _range_score_by_count(
        min_value=CRITICAL_ALERT_SCORE_RANGE[0],
        max_value=CRITICAL_ALERT_SCORE_RANGE[1],
        item_count=critical_count,
        step=5,
    )


def _score_from_warning_alerts(alerts: list[Alert]) -> int:
    warning_count = sum(
        1
        for alert in alerts
        if _is_active_alert(alert) and alert.severity in {SeverityEnum.high, SeverityEnum.medium}
    )
    return _range_score_by_count(
        min_value=WARNING_ALERT_SCORE_RANGE[0],
        max_value=WARNING_ALERT_SCORE_RANGE[1],
        item_count=warning_count,
        step=8,
    )


def calculate_base_score(
    *,
    last_event: Event | None,
    open_incident: Incident | None,
    active_alerts: list[Alert],
) -> int:
    score = SCORE_MAX

    if open_incident is not None:
        if open_incident.severity == SeverityEnum.high:
            score -= 25
        elif open_incident.severity == SeverityEnum.medium:
            score -= 15
        elif open_incident.severity == SeverityEnum.low:
            score -= 8

    if last_event is not None:
        if last_event.event_type == EventTypeEnum.distress:
            score -= 18
        elif last_event.event_type in {EventTypeEnum.wellbeing_check_failed, EventTypeEnum.wellbeing_failure}:
            score -= 12

    minor_active_alerts = sum(
        1 for alert in active_alerts if _is_active_alert(alert) and alert.severity == SeverityEnum.low
    )
    score -= min(10, minor_active_alerts * 5)

    return _clamp_score(score)


def calculate_wellbeing_score(
    *,
    last_event: Event | None,
    open_incident: Incident | None,
    active_alerts: list[Alert],
) -> int:
    # Hierarchical rule: active severe alerts dominate and keep score low/intermediate
    # until they are no longer active.
    if has_critical_alerts(active_alerts):
        return _clamp_score(_score_from_critical_alerts(active_alerts))
    if has_warning_alerts(active_alerts):
        return _clamp_score(_score_from_warning_alerts(active_alerts))
    return calculate_base_score(
        last_event=last_event,
        open_incident=open_incident,
        active_alerts=active_alerts,
    )


def build_user_status(db: Session, user_id: int) -> UserStatusRead | None:
    """Build current status summary for one user.

    Returns None when user does not exist.
    """
    user = db.get(User, user_id)
    if user is None:
        return None

    last_event = db.scalar(
        select(Event)
        .where(Event.user_id == user_id)
        .order_by(Event.created_at.desc(), Event.id.desc())
    )
    open_incident = db.scalar(
        select(Incident)
        .where(Incident.user_id == user_id, Incident.status == IncidentStatusEnum.open)
        .order_by(Incident.opened_at.desc(), Incident.id.desc())
    )
    active_alerts = list(
        db.scalars(
            select(Alert)
            .where(Alert.user_id == user_id, Alert.status.in_(tuple(ACTIVE_ALERT_STATUSES)))
            .order_by(Alert.created_at.desc(), Alert.id.desc())
        ).all()
    )

    current_status = "ok"
    if open_incident is not None and open_incident.severity == SeverityEnum.high:
        current_status = "critical"
    elif open_incident is not None and open_incident.severity == SeverityEnum.medium:
        current_status = "alert"
    elif last_event is not None and last_event.event_type == EventTypeEnum.distress:
        current_status = "warning"

    incident_out = None
    if open_incident is not None:
        incident_out = OpenIncidentStatus(
            id=open_incident.id,
            incident_type=open_incident.incident_type,
            severity=open_incident.severity,
            status=open_incident.status,
            opened_at=open_incident.opened_at,
        )

    wellbeing_score = calculate_wellbeing_score(
        last_event=last_event,
        open_incident=open_incident,
        active_alerts=active_alerts,
    )

    return UserStatusRead(
        user_id=user.id,
        user_name=user.full_name,
        current_status=current_status,
        last_event_type=last_event.event_type if last_event else None,
        last_event_at=last_event.created_at if last_event else None,
        open_incident=incident_out,
        wellbeing_score=wellbeing_score,
        wellbeing_state=score_to_state(wellbeing_score),
    )
