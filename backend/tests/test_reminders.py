import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.db.base import Base, register_models
from app.models.user import User
from app.models.scheduled_reminder import ScheduledReminder

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

def _seed_user(db: Session):
    user = User(full_name="Phase 5 Test User")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def test_reminder_crud():
    db = _build_session()
    user = _seed_user(db)
    
    # 1. Create
    reminder = ScheduledReminder(
        user_id=user.id,
        reminder_type="medication",
        title="Tomar Almax",
        time_of_day="14:00",
        days_of_week=["mon", "tue", "wed"],
        is_active=True
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    
    assert reminder.id is not None
    assert reminder.title == "Tomar Almax"
    assert reminder.last_triggered_at is None
    assert reminder.requires_confirmation is False # Default from model
    
    # 2. Read
    stmt = select(ScheduledReminder).where(ScheduledReminder.user_id == user.id)
    results = db.scalars(stmt).all()
    assert len(results) == 1
    
    # 3. Update
    reminder.title = "Tomar Almax (después de comer)"
    db.commit()
    db.refresh(reminder)
    assert "después de comer" in reminder.title
    
    # 4. Delete
    db.delete(reminder)
    db.commit()
    
    assert db.get(ScheduledReminder, reminder.id) is None
    db.close()

from sqlalchemy import select
