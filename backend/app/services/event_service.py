from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import AlertStatusEnum, EventTypeEnum, IncidentStatusEnum
from app.domain.event_catalog import EventRule, get_input_event_rule, is_derived_internal_event_type
from app.models.alert import Alert
from app.models.device import Device
from app.models.event import Event
from app.models.incident import Incident
from app.schemas.event import EventCreate
from app.services.event_validation import validate_event_semantics
from app.services.metrics_service import increment_counter
import threading
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class UnsupportedEventTypeError(ValueError):
    """Raised when event_type has no rule in the official catalog."""


class TraceIdConflictError(ValueError):
    """Raised when same trace_id is reused with a different payload."""


class EventSemanticValidationError(ValueError):
    """Raised when event payload is semantically inconsistent for its event_type."""


def _payload_json_equal(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    return (left or {}) == (right or {})


def _is_same_logical_payload(*, existing: Event, payload: EventCreate, rule: EventRule, device: Device) -> bool:
    expected_severity = payload.severity or rule.severity
    return all(
        [
            existing.device_id == device.id,
            existing.event_type == payload.event_type,
            existing.severity == expected_severity,
            existing.source == payload.source,
            (existing.user_text or None) == (payload.user_text or None),
            (existing.rita_text or None) == (payload.rita_text or None),
            _payload_json_equal(existing.payload_json, payload.payload_json),
        ]
    )


def _has_recent_duplicate_event(
    db: Session,
    *,
    event_id: int,
    device_id: int,
    event_type: EventTypeEnum,
    dedup_minutes: int,
) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=dedup_minutes)
    existing = db.scalar(
        select(Event)
        .where(
            Event.id != event_id,
            Event.device_id == device_id,
            Event.event_type == event_type,
            Event.created_at >= cutoff,
        )
        .order_by(Event.created_at.desc(), Event.id.desc())
    )
    return existing is not None


def _build_alert_message(event: Event) -> str:
    if event.user_text:
        return event.user_text
    return f"Se ha detectado un evento {event.event_type.value} de severidad {event.severity.value}"


def _validate_event_rule(event_type: EventTypeEnum) -> EventRule:
    rule = get_input_event_rule(event_type)
    if rule is None:
        if is_derived_internal_event_type(event_type):
            raise UnsupportedEventTypeError(
                f"event_type '{event_type.value}' is internal-only and cannot be used as input"
            )
        raise UnsupportedEventTypeError(f"Unsupported event_type: {event_type.value}")
    return rule


def create_event_with_side_effects(
    db: Session,
    payload: EventCreate,
    *,
    device: Device | None = None,
) -> Event | None:
    """Create Event and related Incident/Alert when applicable.

    Returns None when device_code is unknown.
    """
    increment_counter("events_received_total")
    resolved_device = device or db.scalar(select(Device).where(Device.device_code == payload.device_code))
    if resolved_device is None:
        return None

    rule = _validate_event_rule(payload.event_type)
    event_severity = payload.severity or rule.severity
    semantic_error = validate_event_semantics(
        rule=rule,
        event_type=payload.event_type,
        severity=event_severity,
        user_text=payload.user_text,
        payload_json=payload.payload_json,
    )
    if semantic_error is not None:
        increment_counter("events_rejected_semantic_total")
        logger.warning(
            "event_rejected_semantic trace_id=%s event_type=%s device_code=%s reason=%s",
            payload.trace_id,
            payload.event_type.value,
            payload.device_code,
            semantic_error,
        )
        raise EventSemanticValidationError(semantic_error)

    existing_by_trace = db.scalar(select(Event).where(Event.trace_id == str(payload.trace_id)))
    if existing_by_trace is not None:
        if _is_same_logical_payload(
            existing=existing_by_trace,
            payload=payload,
            rule=rule,
            device=resolved_device,
        ):
            increment_counter("events_idempotent_replay_total")
            logger.info(
                "event_idempotent_replay",
                extra={
                    "trace_id": existing_by_trace.trace_id,
                    "event_id": existing_by_trace.id,
                    "device_id": existing_by_trace.device_id,
                },
            )
            return existing_by_trace
        raise TraceIdConflictError(
            f"trace_id '{payload.trace_id}' already exists with a different payload"
        )

    logger.info(
        "event_received",
        extra={
            "trace_id": str(payload.trace_id),
            "event_type": payload.event_type.value,
            "device_id": resolved_device.id,
            "user_id": resolved_device.user_id,
            "source": payload.source,
        },
    )

    event = Event(
        trace_id=str(payload.trace_id),
        user_id=resolved_device.user_id,
        device_id=resolved_device.id,
        event_type=payload.event_type,
        severity=event_severity,
        source=payload.source,
        user_text=payload.user_text,
        rita_text=payload.rita_text,
        payload_json=payload.payload_json,
    )
    db.add(event)
    try:
        db.flush()
        logger.info(
            "event_saved trace_id=%s event_id=%s event_type=%s device_id=%s user_id=%s",
            event.trace_id,
            event.id,
            event.event_type.value,
            event.device_id,
            event.user_id,
        )
    except IntegrityError:
        db.rollback()
        existing_after_race = db.scalar(select(Event).where(Event.trace_id == str(payload.trace_id)))
        if existing_after_race is None:
            raise
        if _is_same_logical_payload(
            existing=existing_after_race,
            payload=payload,
            rule=rule,
            device=resolved_device,
        ):
            increment_counter("events_idempotent_replay_total")
            logger.info(
                "event_idempotent_replay",
                extra={
                    "trace_id": existing_after_race.trace_id,
                    "event_id": existing_after_race.id,
                    "device_id": existing_after_race.device_id,
                },
            )
            return existing_after_race
        raise TraceIdConflictError(
            f"trace_id '{payload.trace_id}' already exists with a different payload"
        )

    is_deduplicated = False
    if rule.dedup_minutes is not None and _has_recent_duplicate_event(
        db,
        event_id=event.id,
        device_id=event.device_id,
        event_type=event.event_type,
        dedup_minutes=rule.dedup_minutes,
    ):
        is_deduplicated = True
        logger.info(
            "event_deduplicated",
            extra={
                "trace_id": event.trace_id,
                "event_id": event.id,
                "event_type": event.event_type.value,
                "device_id": event.device_id,
                "dedup_minutes": rule.dedup_minutes,
            },
        )

    incident: Incident | None = None
    if rule.opens_incident and not is_deduplicated:
        extra = payload.payload_json or {}
        incident = Incident(
            user_id=event.user_id,
            device_id=event.device_id,
            event_id=event.id,
            incident_type=rule.incident_type or event.event_type,
            status=IncidentStatusEnum.open,
            severity=event.severity,
            location=extra.get("location"),
            can_call=extra.get("can_call"),
            summary=event.user_text or f"Incidente de tipo '{(rule.incident_type or event.event_type).value}' detectado automáticamente.",
        )
        db.add(incident)
        db.flush()
        increment_counter("incidents_created_total")
        logger.info(
            "incident_created",
            extra={
                "trace_id": event.trace_id,
                "incident_id": incident.id,
                "event_id": event.id,
                "incident_type": incident.incident_type.value,
                "severity": incident.severity.value,
            },
        )

    if rule.creates_alert and incident is not None:
        alert = Alert(
            user_id=incident.user_id,
            incident_id=incident.id,
            event_id=event.id,
            alert_type=incident.incident_type,
            severity=incident.severity,
            status=AlertStatusEnum.pending,
            message=_build_alert_message(event),
        )
        db.add(alert)
        db.flush()
        increment_counter("alerts_created_total")
        logger.info(
            "alert_created",
            extra={
                "trace_id": event.trace_id,
                "alert_id": alert.id,
                "incident_id": incident.id,
                "event_id": event.id,
                "severity": alert.severity.value,
            },
        )

    db.commit()
    db.refresh(event)

    # 4. BACKGROUND AI ANALYSIS (Best Effort)
    # - user_speech is handled synchronously in create_event (API layer) because the device
    #   needs RITA's response in the HTTP response body. It goes through ConversationService.
    # - Simulation events are handled synchronously in the API layer to return immediate feedback.
    if event.event_type in {EventTypeEnum.checkin, EventTypeEnum.help_request} and event.source != "simulation-ui":
        _trigger_background_analysis(event.id)

    return event


def _trigger_background_analysis(event_id: int) -> None:
    """
    Launches AI analysis in a background thread to avoid blocking the main ingestion flow.
    """
    def _run():
        import asyncio
        from app.services.check_in_analysis_service import CheckInAnalysisService
        
        db = SessionLocal()
        try:
            # Start a local loop for the async service in this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            service = CheckInAnalysisService(db)
            event = db.get(Event, event_id)
            if event:
                loop.run_until_complete(service.analyze_event_check_in(event))
            
            loop.close()
        except Exception as e:
            logger.error(f"Error in background AI analysis for event_id={event_id}: {e}")
        finally:
            db.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
