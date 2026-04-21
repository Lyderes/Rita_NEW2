import pytest
import uuid
from datetime import date, datetime, UTC
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
from app.db.base import Base, register_models
from app.models.user import User
from app.models.device import Device
from app.models.event import Event
from app.models.check_in_analysis import CheckInAnalysis
from app.models.user_interpretation_settings import UserInterpretationSettings
from app.models.user_baseline_profile import UserBaselineProfile
from app.domain.enums import EventTypeEnum, SeverityEnum
from app.services.daily_score_service import DailyScoringService

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

def _seed_data(db: Session):
    user = User(full_name="Test Person Phase 4")
    db.add(user)
    db.flush()
    
    baseline = UserBaselineProfile(user_id=user.id, usual_mood="positive")
    db.add(baseline)
    
    settings = UserInterpretationSettings(user_id=user.id)
    db.add(settings)
    
    device = Device(
        user_id=user.id,
        device_code=f"test-device-{uuid.uuid4()}",
        device_name="Test Device",
        is_active=True
    )
    db.add(device)
    db.commit()
    db.refresh(user)
    db.refresh(device)
    return user, device

def add_analysis(db: Session, user_id: int, device_id: int, signals: list[str], risk: str, created_at: datetime):
    trace_id = str(uuid.uuid4())
    event = Event(
        user_id=user_id,
        device_id=device_id,
        event_type=EventTypeEnum.checkin,
        severity=SeverityEnum.low,
        trace_id=trace_id,
        source="rita-edge"
    )
    db.add(event)
    db.flush()
    
    analysis = CheckInAnalysis(
        event_id=event.id,
        risk=risk,
        signals=signals,
        summary=f"Analysis for {signals}",
        model_used="rule_based",
    )
    db.add(analysis)
    db.commit()

def test_sensitivity_modes_tier_selection():
    db = _build_session()
    user, device = _seed_data(db)
    service = DailyScoringService(db)
    today = date.today()

    add_analysis(db, user.id, device.id, ["pain"], "medium", datetime.now(UTC))

    # 1. Balanced Mode — 1 pain signal at medium risk gives a deviation score (60-84)
    user.interpretation_settings.sensitivity_mode = "balanced"
    db.commit()

    score_balanced = service.compute_daily_score(user.id, today)
    balanced_score_value = score_balanced.global_score  # snapshot before ORM mutation
    assert 50 <= balanced_score_value <= 84

    # 2. Sensitive Mode — same signal should score lower or produce a different narrative
    user.interpretation_settings.sensitivity_mode = "sensitive"
    db.commit()

    score_sensitive = service.compute_daily_score(user.id, today)
    sensitive_score_value = score_sensitive.global_score
    # Sensitive mode applies a 1.2× penalty multiplier, so score must be ≤ balanced
    assert sensitive_score_value <= balanced_score_value
    db.close()


def test_chronic_pain_mitigation():
    db = _build_session()
    user, device = _seed_data(db)
    service = DailyScoringService(db)
    today = date.today()

    add_analysis(db, user.id, device.id, ["pain"], "medium", datetime.now(UTC))

    # Compute baseline score and snapshot the value before ORM object is reused
    score_normal = service.compute_daily_score(user.id, today)
    normal_score_value = score_normal.global_score  # snapshot: compute_daily_score reuses the same ORM object

    # Enable chronic pain mitigation — pain base penalty drops from 10 to 4
    user.interpretation_settings.has_chronic_pain = True
    db.commit()

    score_chronic = service.compute_daily_score(user.id, today)
    assert score_chronic.global_score > normal_score_value
    db.close()


def test_recovery_with_personalization():
    db = _build_session()
    user, device = _seed_data(db)
    service = DailyScoringService(db)
    today = date.today()

    # Balanced mode: threshold_critical=40. tiredness/medium → penalty=5, ok → penalty=8.
    # global_score = 80 - 5 - 8 = 67 > 40, so recovery is NOT suppressed.
    user.interpretation_settings.sensitivity_mode = "balanced"
    db.commit()

    add_analysis(db, user.id, device.id, ["tiredness"], "medium", datetime.now(UTC))
    add_analysis(db, user.id, device.id, ["ok"], "low", datetime.now(UTC))

    score = service.compute_daily_score(user.id, today)
    # Recovery detected: bad start followed by positive last check-in
    # Narrative uses "mejor" (e.g. "algo mejor" or "mejorado")
    assert "mejor" in score.narrative_summary or "recuperaci" in score.narrative_summary
    db.close()
