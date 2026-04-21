
import sys
import uuid
from pathlib import Path
from datetime import date, datetime, UTC

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models.user import User
from app.models.device import Device
from app.models.user_baseline_profile import UserBaselineProfile
from app.models.check_in_analysis import CheckInAnalysis
from app.models.event import Event
from app.models.daily_score import DailyScore
from app.services.daily_score_service import DailyScoringService
from app.domain.enums import EventTypeEnum, SeverityEnum

def setup_test_user(db):
    user = db.query(User).filter(User.full_name == "Test User Phase 3").first()
    if not user:
        user = User(full_name="Test User Phase 3")
        db.add(user)
        db.commit()
        db.refresh(user)
    
    device = db.query(Device).filter(Device.user_id == user.id).first()
    if not device:
        device = Device(
            user_id=user.id,
            device_code="test_code_phase3",
            device_name="Test Device Phase 3",
            is_active=True
        )
        db.add(device)
        db.commit()
        db.refresh(device)
    
    baseline = db.query(UserBaselineProfile).filter(UserBaselineProfile.user_id == user.id).first()
    if not baseline:
        baseline = UserBaselineProfile(
            user_id=user.id,
            usual_mood="positive",
            usual_activity_level="medium",
            usual_energy_level="medium"
        )
        db.add(baseline)
        db.commit()
    
    return user, device

def mock_checkin(db, user, device, text, mood, signals, risk):
    event = Event(
        trace_id=str(uuid.uuid4()),
        user_id=user.id,
        device_id=device.id,
        event_type=EventTypeEnum.user_speech,
        severity=SeverityEnum.low,
        payload_json={"user_text": text},
        user_text=text,
        created_at=datetime.now(UTC)
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    
    analysis = CheckInAnalysis(
        event_id=event.id,
        text=text,
        summary=f"Mock summary: {text}",
        mood=mood,
        signals=signals,
        risk=risk,
        model_used="mock"
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis

def test_scenarios():
    db = SessionLocal()
    try:
        user, device = setup_test_user(db)
        service = DailyScoringService(db)
        today = date.today()

        # Cleanup today's scores and events for this user to start fresh
        db.query(DailyScore).filter(DailyScore.user_id == user.id).delete()
        db.query(CheckInAnalysis).filter(CheckInAnalysis.event_id.in_(
            db.query(Event.id).filter(Event.user_id == user.id)
        )).delete(synchronize_session=False)
        db.query(Event).filter(Event.user_id == user.id).delete()
        db.commit()

        print("--- Scenario 1: Normal Day ---")
        mock_checkin(db, user, device, "Me siento muy bien", "positive", [], "low")
        score = service.compute_daily_score(user.id, today)
        print(f"Score: {score.global_score}")
        print(f"Narrative: {score.narrative_summary}")
        print(f"Factors: {score.main_factors}")

        print("\n--- Scenario 2: Mild Concern (Pain) ---")
        mock_checkin(db, user, device, "Me duele un poco la pierna", "neutral", ["pain"], "medium")
        score = service.compute_daily_score(user.id, today)
        print(f"Score: {score.global_score}")
        print(f"Narrative: {score.narrative_summary}")
        print(f"Factors: {score.main_factors}")

        print("\n--- Scenario 3: Moderate Concern (Dizziness + Repetition) ---")
        mock_checkin(db, user, device, "Me siento mareada", "low", ["dizziness"], "high")
        mock_checkin(db, user, device, "Sigo con mareos", "low", ["dizziness"], "high")
        score = service.compute_daily_score(user.id, today)
        print(f"Score: {score.global_score}")
        print(f"Narrative: {score.narrative_summary}")
        print(f"Factors: {score.main_factors}")

        print("\n--- Result Summary ---")
        print(f"Final Global Score: {score.global_score}")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_scenarios()
