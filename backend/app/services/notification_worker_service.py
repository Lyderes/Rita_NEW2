from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.enums import NotificationChannelEnum, NotificationJobStatusEnum
from app.models.notification_job import NotificationJob
from app.services.notifications.providers.fcm_provider import FCMProvider
from app.services.notifications.providers.twilio_provider import TwilioProvider

import logging
logger = logging.getLogger(__name__)

_fcm_provider: FCMProvider | None = None
_twilio_provider: TwilioProvider | None = None

def _get_fcm() -> FCMProvider:
    global _fcm_provider
    if _fcm_provider is None:
        _fcm_provider = FCMProvider()
    return _fcm_provider

def _get_twilio() -> TwilioProvider:
    global _twilio_provider
    if _twilio_provider is None:
        _twilio_provider = TwilioProvider()
    return _twilio_provider

@dataclass(slots=True)
class NotificationWorkerResult:
    scanned_eligible_jobs: int
    processed_jobs: int
    sent_jobs: int
    rescheduled_jobs: int
    terminal_failed_jobs: int

def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

def process_notification(job: NotificationJob) -> tuple[bool, str | None, str | None]:
    payload = job.payload_json or {}
    try:
        if job.channel == NotificationChannelEnum.push:
            target_token = payload.get("fcm_token")
            if not target_token:
                return False, "No FCM token in payload — push skipped", None
            provider = _get_fcm()
            data = {
                "alert_id": str(payload.get("alert_id", "")),
                "severity": payload.get("severity", ""),
                "incident_id": str(payload.get("incident_id", ""))
            }
            resp = provider.send_push(
                title="Nueva Alerta RITA",
                body=payload.get("message", "Alerta detectada"),
                data=data,
                target_token=target_token
            )
            return True, None, resp
            
        elif job.channel == NotificationChannelEnum.sms:
            provider = _get_twilio()
            to_number = payload.get("phone_number", "+34600000000")
            resp = provider.send_sms(
                text=payload.get("message", "Alerta detectada"),
                to_number=to_number
            )
            return True, None, resp
            
        elif job.channel in (NotificationChannelEnum.mock, NotificationChannelEnum.mock_priority):
            if bool(payload.get("force_fail")):
                return False, "forced failure by payload.force_fail", None
            return True, None, "mock_success"
            
        return False, f"Unsupported channel: {job.channel}", None
    except Exception as e:
        logger.error(f"Notification processing error: {e}")
        return False, str(e), None


def run_notification_worker_once(
    db: Session,
    *,
    now: datetime | None = None,
    batch_size: int = 100,
    base_backoff_seconds: int = 30,
) -> NotificationWorkerResult:
    current_time = _normalize_timestamp(now) or datetime.now(UTC)
    jobs = list(
        db.scalars(
            select(NotificationJob)
            .where(
                NotificationJob.status == NotificationJobStatusEnum.pending,
                or_(
                    NotificationJob.next_attempt_at.is_(None),
                    NotificationJob.next_attempt_at <= current_time,
                ),
            )
            .order_by(NotificationJob.next_attempt_at.asc(), NotificationJob.created_at.asc(), NotificationJob.id.asc())
            .limit(max(batch_size, 1))
        ).all()
    )

    sent_jobs = 0
    rescheduled_jobs = 0
    terminal_failed_jobs = 0

    for job in jobs:
        job.last_attempt_at = current_time
        is_ok, error, provider_response = process_notification(job)
        if provider_response:
            job.provider_response = provider_response
            
        if is_ok:
            job.status = NotificationJobStatusEnum.sent
            job.processed_at = current_time
            job.next_attempt_at = None
            job.last_error = None
            db.add(job)
            sent_jobs += 1
            continue

        attempt_number = (job.retry_count or 0) + 1
        job.retry_count = attempt_number
        job.last_error = error or "unknown error"
        
        if attempt_number > max(job.max_retries, 0):
            job.status = NotificationJobStatusEnum.failed
            job.processed_at = current_time
            job.next_attempt_at = None
            db.add(job)
            terminal_failed_jobs += 1
            continue

        per_job_base_backoff = max(job.base_backoff_seconds or base_backoff_seconds, 1)
        delay_seconds = per_job_base_backoff * (2 ** (attempt_number - 1))
        job.status = NotificationJobStatusEnum.pending
        job.next_attempt_at = current_time + timedelta(seconds=delay_seconds)
        job.processed_at = None
        db.add(job)
        rescheduled_jobs += 1

    if jobs:
        db.commit()

    return NotificationWorkerResult(
        scanned_eligible_jobs=len(jobs),
        processed_jobs=len(jobs),
        sent_jobs=sent_jobs,
        rescheduled_jobs=rescheduled_jobs,
        terminal_failed_jobs=terminal_failed_jobs,
    )
