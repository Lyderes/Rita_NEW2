import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.services.ai.rule_based_analysis import normalize_analysis, run_rule_based_analysis
from app.api.deps import require_frontend_auth

# Setup test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_hardening.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_overrides():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_frontend_auth] = lambda: "test_user"
    yield
    app.dependency_overrides.clear()

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # Pre-seed a user and device for simulation
    with TestingSessionLocal() as db:
        from app.models.user import User
        from app.models.device import Device
        user = User(id=1, full_name="Test User")
        db.add(user)
        db.commit()
        device = Device(id=1, user_id=1, device_code="DEV001", device_name="Test Device", is_active=True)
        db.add(device)
        db.commit()
    yield

def test_normalization_logic():
    """Test the normalization layer independently."""
    raw = {
        "summary": "High risk",
        "risk": "High",
        "signals": ["pain"],
        "mood": "Triste"
    }
    norm = normalize_analysis(raw)
    assert norm["risk"] == "high"
    assert norm["mood"] == "low"
    assert "pain" in norm["signals"]
    assert isinstance(norm["signals"], list)

def test_rule_based_scenarios():
    """Test specific keywords."""
    # Scenario 1: Pain & Dizziness
    res = run_rule_based_analysis("Me duele la espalda y estoy mareada")
    assert "pain" in res["signals"]
    assert "dizziness" in res["signals"]
    assert res["risk"] == "high"
    
    # Scenario 2: Emergency
    res = run_rule_based_analysis("Ayuda, me he caido")
    assert "fall" in res["signals"]
    assert "urgency" in res["signals"]
    assert res["risk"] == "high"

def test_simulation_endpoint_hardening():
    """Test the POST /events/checkin with various inputs."""
    # Test 1: Empty text
    resp = client.post("/events/checkin", json={"user_id": 1, "text": ""})
    assert resp.status_code == 400
    
    # Test 2: Normal text
    resp = client.post("/events/checkin", json={"user_id": 1, "text": "Me duele el pecho"})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "analysis" in data
    assert data["analysis"]["risk"] == "medium"
    assert "pain" in data["analysis"]["signals"]
    assert data["analysis"]["mood"] == "neutral"

    # Test 3: Unknown sentiment
    resp = client.post("/events/checkin", json={"user_id": 1, "text": "La mesa es verde"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["analysis"]["risk"] == "low"
    assert data["analysis"]["signals"] == []
    assert data["analysis"]["mood"] == "neutral"

    resp = client.post("/events/checkin", json={"user_id": 999, "text": "Ola"})
    assert resp.status_code == 400
