import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.db.session import get_db
from app.main import app
from app.models.event import Event
from app.models.check_in_analysis import CheckInAnalysis
from app.models.user import User
from app.models.device import Device

@pytest.fixture
def client_ctx():
    register_models()
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    db = session_local()
    
    # Setup test data
    user = User(full_name="Simulation Test User")
    db.add(user)
    db.flush()
    device = Device(user_id=user.id, device_code="sim-001", device_name="Sim Device", is_active=True)
    db.add(device)
    db.commit()
    
    with TestClient(app) as client:
        # Login to get token
        login_resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        yield client, db, user, headers
        
    app.dependency_overrides.clear()
    db.close()

def test_simulate_checkin_flow(client_ctx):
    client, db, user, headers = client_ctx
    
    test_phrases = [
        "Hoy estoy bien",
        "Estoy cansada",
        "Me duele la espalda",
        "No tengo ganas de hablar",
        "Estoy mareada",
    ]
    
    for phrase in test_phrases:
        response = client.post(
            "/events/checkin",
            headers=headers,
            json={"user_id": user.id, "text": phrase}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "analysis" in data
        assert data["analysis"]["summary"] is not None
        
        # Verify persistence in DB
        event_id = int(data["id"])
        db.expire_all() # Ensure we get fresh data
        event = db.get(Event, event_id)
        assert event is not None
        assert event.user_text == phrase
        
        analysis = db.scalar(select(CheckInAnalysis).where(CheckInAnalysis.event_id == event_id))
        assert analysis is not None
        assert analysis.risk == data["analysis"]["risk"]
        
        if "espalda" in phrase or "duele" in phrase:
            assert analysis.risk == "medium"
            assert "pain" in analysis.signals
        elif "mareada" in phrase:
            assert analysis.risk == "high"
            assert "dizziness" in analysis.signals

    print("\nPhase 1 Simulation Flow Validated Successfully.")
