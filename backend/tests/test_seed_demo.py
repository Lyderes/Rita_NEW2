"""
Tests para scripts/seed_demo.py

Usa SQLite en memoria igual que los otros tests del proyecto.
No ejecuta el script como subproceso: importa y llama las funciones
directamente para que los errores sean claros y el test sea rápido.
"""
from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base, register_models
from app.domain.enums import AlertStatusEnum, IncidentStatusEnum
from app.models.alert import Alert
from app.models.device import Device
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User
from scripts.seed_demo import DEMO_DEVICES, DEMO_USERS, reset_demo, seed


def _build_session() -> Session:
    register_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return factory()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _user_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User)) or 0


def _device_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Device)) or 0


def _event_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Event)) or 0


def _incident_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Incident)) or 0


def _alert_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Alert)) or 0


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_seed_creates_all_demo_users() -> None:
    db = _build_session()
    seed(db)
    assert _user_count(db) == len(DEMO_USERS)


def test_seed_creates_all_demo_devices() -> None:
    db = _build_session()
    seed(db)
    assert _device_count(db) == len(DEMO_DEVICES)


def test_seed_creates_events() -> None:
    """Al menos un evento debe haberse creado."""
    db = _build_session()
    seed(db)
    assert _event_count(db) > 0


def test_seed_creates_at_least_one_open_incident() -> None:
    db = _build_session()
    seed(db)
    open_count = db.scalar(
        select(func.count())
        .select_from(Incident)
        .where(Incident.status == IncidentStatusEnum.open)
    )
    assert (open_count or 0) >= 1


def test_seed_creates_at_least_one_pending_alert() -> None:
    db = _build_session()
    seed(db)
    pending_count = db.scalar(
        select(func.count())
        .select_from(Alert)
        .where(Alert.status == AlertStatusEnum.pending)
    )
    assert (pending_count or 0) >= 1


def test_seed_is_idempotent_users() -> None:
    """Ejecutar seed dos veces no duplica usuarios."""
    db = _build_session()
    seed(db)
    count_first = _user_count(db)
    seed(db)
    count_second = _user_count(db)
    assert count_first == count_second


def test_seed_is_idempotent_devices() -> None:
    """Ejecutar seed dos veces no duplica dispositivos."""
    db = _build_session()
    seed(db)
    count_first = _device_count(db)
    seed(db)
    count_second = _device_count(db)
    assert count_first == count_second


def test_seed_is_idempotent_events() -> None:
    """Ejecutar seed dos veces no duplica eventos (la segunda vez salta al ver que ya existen)."""
    db = _build_session()
    seed(db)
    count_first = _event_count(db)
    seed(db)
    count_second = _event_count(db)
    assert count_first == count_second


def test_reset_removes_demo_data() -> None:
    """reset_demo borra todos los datos demo."""
    db = _build_session()
    seed(db)
    assert _user_count(db) > 0
    reset_demo(db)
    assert _user_count(db) == 0


def test_reset_then_reseed() -> None:
    """Después de reset, seed vuelve a crear los datos completos."""
    db = _build_session()
    seed(db)
    users_after_first_seed = _user_count(db)
    reset_demo(db)
    seed(db)
    assert _user_count(db) == users_after_first_seed
