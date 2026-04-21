import uuid
from datetime import datetime, time, UTC
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scheduled_reminder import ScheduledReminder
from app.models.event import Event
from app.models.device import Device
from app.domain.enums import EventTypeEnum, SeverityEnum

class ReminderTriggerService:
    def __init__(self, db: Session):
        self.db = db

    def evaluate_reminders(self, current_time_utc: datetime = None) -> list[Event]:
        """
        Iterates through active reminders and triggers those that are due.
        """
        if current_time_utc is None:
            current_time_utc = datetime.now(UTC)
        
        today = current_time_utc.date()
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        target_day_name = day_names[today.weekday()]
        now_hh_mm = current_time_utc.strftime("%H:%M")

        stmt = select(ScheduledReminder).where(ScheduledReminder.is_active == True)
        active_reminders = self.db.scalars(stmt).all()
        
        triggered_events = []

        for r in active_reminders:
            # 1. Day check
            if target_day_name not in r.days_of_week:
                continue

            # 2. Time check (HH:mm)
            # We trigger if current_time >= scheduled_time
            if now_hh_mm < r.time_of_day:
                continue

            # 3. Idempotency check: has it been triggered today?
            if r.last_triggered_at:
                # Convert to UTC to be safe if it's naive (though model says timezone=True)
                lt_at = r.last_triggered_at
                if lt_at.tzinfo is None:
                    lt_at = lt_at.replace(tzinfo=UTC)
                
                if lt_at.date() >= today:
                    continue

            # 4. Trigger!
            # Find a device for the event (Requirement: Event belongs to a device)
            device = self.db.scalar(
                select(Device).where(Device.user_id == r.user_id).order_by(Device.id.asc())
            )
            if not device:
                # Should not happen in a healthy system, but skip if no device
                continue

            event = Event(
                trace_id=str(uuid.uuid4()),
                user_id=r.user_id,
                device_id=device.id,
                event_type=EventTypeEnum.reminder_triggered,
                severity=SeverityEnum.low,
                source="rita-system",
                rita_text=f"Recordatorio: {r.title}",
                payload_json={
                    "reminder_id": r.id,
                    "reminder_type": r.reminder_type,
                    "title": r.title,
                    "confirmation_status": "pending" if r.requires_confirmation else "none"
                },
                created_at=current_time_utc
            )
            self.db.add(event)
            triggered_events.append(event)

            # Update last_triggered_at
            r.last_triggered_at = current_time_utc

        if triggered_events:
            self.db.commit()

        return triggered_events
