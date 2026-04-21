import pytest
import uuid
from datetime import date, datetime, time, UTC, timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from app.db.base import Base, register_models
from app.models.user import User
from app.models.event import Event
from app.models.scheduled_reminder import ScheduledReminder
from app.models.device import Device
from app.domain.enums import EventTypeEnum, SeverityEnum
from app.services.reminder_trigger_service import ReminderTriggerService

def _build_session() -> Session:
    register_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_local()

def _setup_user(db: Session):
    user = User(full_name="Phase 7.2 Test User")
    db.add(user)
    db.commit()
    device = Device(user_id=user.id, device_name="Test Gateway", device_code=str(uuid.uuid4()))
    db.add(device)
    db.commit()
    return user, device

def _add_reminder(db: Session, user_id: int, r_type: str, r_time: str, days=None, requires_confirmation=False):
    reminder = ScheduledReminder(
        user_id=user_id,
        reminder_type=r_type,
        time_of_day=r_time,
        days_of_week=days or ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        is_active=True,
        requires_confirmation=requires_confirmation,
        title=f"Test {r_type}"
    )
    db.add(reminder)
    db.commit()
    return reminder

def test_reminder_triggers_on_time():
    db = _build_session()
    user, device = _setup_user(db)
    _add_reminder(db, user.id, "medication", "08:00")
    now = datetime.combine(date.today(), time(8, 5)).replace(tzinfo=UTC)
    service = ReminderTriggerService(db)
    events = service.evaluate_reminders(current_time_utc=now)
    assert len(events) == 1
    assert events[0].event_type == EventTypeEnum.reminder_triggered
    db.close()

def test_reminder_no_trigger_if_early():
    db = _build_session()
    user, device = _setup_user(db)
    _add_reminder(db, user.id, "meal", "12:00")
    now = datetime.combine(date.today(), time(11, 59)).replace(tzinfo=UTC)
    service = ReminderTriggerService(db)
    events = service.evaluate_reminders(current_time_utc=now)
    assert len(events) == 0
    db.close()

def test_reminder_day_check():
    db = _build_session()
    user, device = _setup_user(db)
    today = date(2024, 3, 26) # Tuesday
    _add_reminder(db, user.id, "hydration", "08:00", days=["mon"])
    now = datetime.combine(today, time(9, 0)).replace(tzinfo=UTC)
    service = ReminderTriggerService(db)
    events = service.evaluate_reminders(current_time_utc=now)
    assert len(events) == 0
    db.close()

def test_reminder_triggers_on_second_day():
    db = _build_session()
    user, device = _setup_user(db)
    reminder = _add_reminder(db, user.id, "medication", "08:00")
    day1 = datetime(2024, 3, 25, 8, 5, tzinfo=UTC)
    service = ReminderTriggerService(db)
    service.evaluate_reminders(current_time_utc=day1)
    db.expire_all()
    reminder = db.get(ScheduledReminder, 1)
    assert reminder.last_triggered_at.date() == day1.date()
    day2 = day1 + timedelta(days=1)
    events = service.evaluate_reminders(current_time_utc=day2)
    assert len(events) == 1
    db.close()

def test_reminder_confirmation_workflow():
    db = _build_session()
    user, device = _setup_user(db)
    
    # 1. Trigger reminder that REQUIRES confirmation
    _add_reminder(db, user.id, "medication", "08:00", requires_confirmation=True)
    now = datetime.combine(date.today(), time(8, 5)).replace(tzinfo=UTC)
    
    service = ReminderTriggerService(db)
    triggered_events = service.evaluate_reminders(current_time_utc=now)
    
    assert len(triggered_events) == 1
    event = triggered_events[0]
    assert event.payload_json["confirmation_status"] == "pending"
    assert "Pendiente de confirmar" in event.human_description

    # 2. Confirm it (using the logic from the endpoint)
    from sqlalchemy.orm.attributes import flag_modified
    
    target_event = db.get(Event, event.id)
    payload = target_event.payload_json
    payload["confirmation_status"] = "confirmed"
    payload["confirmed_at"] = datetime.now(UTC).isoformat()
    target_event.payload_json = payload
    flag_modified(target_event, "payload_json")
    
    conf_event = Event(
        trace_id=str(uuid.uuid4()), user_id=user.id, device_id=device.id,
        event_type=EventTypeEnum.reminder_confirmed, severity=SeverityEnum.low,
        source="rita-frontend", payload_json={"title": "Test medication"},
        created_at=datetime.now(UTC)
    )
    db.add(conf_event)
    db.commit()
    
    # 3. Verify
    db.refresh(target_event)
    assert target_event.payload_json["confirmation_status"] == "confirmed"
    assert "Confirmado" in target_event.human_description
    
    db.close()

def test_reminder_without_confirmation():
    db = _build_session()
    user, device = _setup_user(db)
    _add_reminder(db, user.id, "meal", "12:00", requires_confirmation=False)
    now = datetime.combine(date.today(), time(12, 5)).replace(tzinfo=UTC)
    service = ReminderTriggerService(db)
    events = service.evaluate_reminders(current_time_utc=now)
    assert len(events) == 1
    assert events[0].payload_json["confirmation_status"] == "none"
    db.close()
