from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.models.device import Device
from app.models.user import User


@pytest.fixture(autouse=True)
def patch_test_auth_credentials():
    """Patch settings so the auth fallback accepts admin/admin123.

    Tests use in-memory SQLite DBs with no FrontendUser seeded, so
    _authenticate_login falls back to verify_frontend_credentials which
    reads settings.frontend_password.  The .env default is not 'admin123',
    so without this patch every test that calls /auth/login gets a 401.
    """
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.frontend_password
    object.__setattr__(settings, "frontend_password", "admin123")
    yield
    object.__setattr__(settings, "frontend_password", original)


@pytest.fixture
def db_session() -> Session:
    register_models()
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = SessionLocal()
    
    # Seed baseline data
    user = User(full_name="E2E Test User", notes="E2E")
    db.add(user)
    db.flush()
    device = Device(user_id=user.id, device_code="e2e-device-01", device_name="Test Device 1", is_active=True)
    db.add(device)
    db.commit()
    
    yield db
    db.close()
