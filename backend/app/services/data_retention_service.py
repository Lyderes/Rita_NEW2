import logging
from datetime import datetime, timedelta, UTC

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.event import Event
from app.models.alert import Alert
from app.models.notification_job import NotificationJob
from app.domain.enums import AlertStatusEnum

logger = logging.getLogger(__name__)

def run_data_retention(db: Session, now_override: datetime | None = None) -> dict[str, int]:
    """
    Deletes old records according to the expiration policies defined in environment variables.
    """
    settings = get_settings()
    if not settings.enable_data_retention:
        logger.info("Data retention is disabled in configuration. Skipping.")
        return {"events_deleted": 0, "jobs_deleted": 0, "alerts_deleted": 0}

    now = now_override or datetime.now(UTC)
    
    events_cutoff = now - timedelta(days=settings.data_retention_events_days)
    stmt_events = delete(Event).where(Event.created_at < events_cutoff)
    
    jobs_cutoff = now - timedelta(days=settings.data_retention_notification_jobs_days)
    stmt_jobs = delete(NotificationJob).where(NotificationJob.created_at < jobs_cutoff)
    
    alerts_cutoff = now - timedelta(days=settings.data_retention_closed_alerts_days)
    stmt_alerts = delete(Alert).where(
        Alert.status == AlertStatusEnum.resolved,
        Alert.created_at < alerts_cutoff
    )
    
    try:
        events_res = db.execute(stmt_events)
        jobs_res = db.execute(stmt_jobs)
        alerts_res = db.execute(stmt_alerts)
        db.commit()
        
        summary = {
            "events_deleted": events_res.rowcount,
            "jobs_deleted": jobs_res.rowcount,
            "alerts_deleted": alerts_res.rowcount,
        }
        logger.info("Data retention cycle completed", extra=summary)
        return summary
    except Exception as e:
        db.rollback()
        logger.error(f"Failed data retention cycle: {e}")
        raise
