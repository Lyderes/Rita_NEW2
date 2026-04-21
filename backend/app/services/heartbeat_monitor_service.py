from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import DeviceAdminStatusEnum, EventTypeEnum
from app.models.device import Device
from app.models.event import Event
from app.schemas.event import EventCreate
from app.services.event_service import create_event_with_side_effects

_TRACE_NAMESPACE = UUID("34f6251e-0f69-47db-9ef2-3e4a25c86f73")


@dataclass(slots=True)
class HeartbeatMonitorResult:
    scanned_devices: int
    offline_candidates: int
    events_created: int
    idempotent_replays: int
    skipped_recent_or_not_due: int


def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _floor_to_window(value: datetime, window_minutes: int) -> datetime:
    window_seconds = max(window_minutes, 1) * 60
    epoch = int(value.timestamp())
    floored_epoch = epoch - (epoch % window_seconds)
    return datetime.fromtimestamp(floored_epoch, tz=UTC)


def _build_trace_id(*, device_code: str, bucket_start: datetime) -> UUID:
    key = f"device_offline:{device_code}:{bucket_start.isoformat()}"
    return uuid5(_TRACE_NAMESPACE, key)


def _build_payload(
    *,
    device: Device,
    trace_id: UUID,
    source: str,
    now: datetime,
    reason: str,
) -> EventCreate:
    payload_json: dict[str, Any] = {
        "reason": reason,
        "monitor_checked_at": now.isoformat(),
        "last_seen_at": _normalize_timestamp(device.last_seen_at).isoformat()
        if device.last_seen_at is not None
        else None,
        "device_name": device.device_name,
    }
    return EventCreate(
        schema_version="1.0",
        trace_id=trace_id,
        device_code=device.device_code,
        event_type=EventTypeEnum.device_offline,
        source=source,
        user_text=f"Device {device.device_code} heartbeat is offline",
        payload_json=payload_json,
    )


def run_heartbeat_monitor_once(
    db: Session,
    *,
    now: datetime | None = None,
    offline_threshold_minutes: int = 30,
    no_heartbeat_grace_minutes: int = 30,
    source: str = "heartbeat-monitor",
) -> HeartbeatMonitorResult:
    current_time = _normalize_timestamp(now) or datetime.now(UTC)
    offline_cutoff = current_time - timedelta(minutes=offline_threshold_minutes)
    never_seen_cutoff = current_time - timedelta(minutes=no_heartbeat_grace_minutes)

    devices = list(
        db.scalars(
            select(Device).where(
                Device.is_active.is_(True),
                Device.admin_status == DeviceAdminStatusEnum.active,
            )
        ).all()
    )

    offline_candidates = 0
    events_created = 0
    idempotent_replays = 0
    skipped_recent_or_not_due = 0

    for device in devices:
        last_seen = _normalize_timestamp(device.last_seen_at)
        provisioned = _normalize_timestamp(device.provisioned_at)
        created = _normalize_timestamp(device.created_at)
        reference_when_never_seen = provisioned or created or current_time

        if last_seen is None:
            if reference_when_never_seen > never_seen_cutoff:
                skipped_recent_or_not_due += 1
                continue
            bucket_anchor = reference_when_never_seen
            reason = "never_seen_grace_elapsed"
        else:
            if last_seen > offline_cutoff:
                skipped_recent_or_not_due += 1
                continue
            bucket_anchor = last_seen
            reason = "heartbeat_expired"

        offline_candidates += 1
        bucket_start = _floor_to_window(bucket_anchor, offline_threshold_minutes)
        trace_id = _build_trace_id(device_code=device.device_code, bucket_start=bucket_start)
        trace_str = str(trace_id)
        existed_before = db.scalar(select(Event.id).where(Event.trace_id == trace_str)) is not None

        if existed_before:
            idempotent_replays += 1
            continue

        payload = _build_payload(
            device=device,
            trace_id=trace_id,
            source=source,
            now=current_time,
            reason=reason,
        )
        create_event_with_side_effects(db, payload, device=device)
        events_created += 1

    return HeartbeatMonitorResult(
        scanned_devices=len(devices),
        offline_candidates=offline_candidates,
        events_created=events_created,
        idempotent_replays=idempotent_replays,
        skipped_recent_or_not_due=skipped_recent_or_not_due,
    )
