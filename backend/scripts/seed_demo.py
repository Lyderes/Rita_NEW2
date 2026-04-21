"""
Script de seed de datos demo para RITA backend.

Crea un conjunto de datos coherentes y variados para probar el sistema sin
tener que crear nada a mano.  Es razonablemente idempotente: identifica los
datos de demo por device_code y user full_name fijos, y solo inserta los que
faltan.

Uso
---
    # Local (desde backend/):
    python scripts/seed_demo.py

    # Con reset previo (borra y recrea todos los datos demo):
    python scripts/seed_demo.py --reset

    # En Docker:
    docker compose run --rm backend python scripts/seed_demo.py
    docker compose run --rm backend python scripts/seed_demo.py --reset
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# Permite ejecutar desde la raíz del repo o desde backend/
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import register_models  # noqa: E402
from app.domain.enums import (  # noqa: E402
    EventTypeEnum,
    IncidentStatusEnum,
    SeverityEnum,
)
from app.models.device import Device  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.incident import Incident  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.event_service import create_event_with_side_effects  # noqa: E402
from app.schemas.event import EventCreate  # noqa: E402

register_models()

# ---------------------------------------------------------------------------
# Identificadores fijos de demo — permiten la idempotencia
# ---------------------------------------------------------------------------
DEMO_USERS: list[dict] = [
    {"full_name": "Demo :: Ana García", "notes": "Usuario sin actividad reciente"},
    {"full_name": "Demo :: Carlos López", "notes": "Usuario con incidente abierto y alerta pendiente"},
    {"full_name": "Demo :: María Torres", "notes": "Usuario con alertas pendientes, sin incidente abierto"},
]

DEMO_DEVICES: list[dict] = [
    # (user_full_name, device_code, device_name, location, last_seen_offset_minutes)
    # last_seen_offset_minutes=None → nunca visto (offline)
    # offset < 5 → online  |  5-30 → stale  |  >30 → offline
    {"user": "Demo :: Ana García",    "code": "demo-device-ana",    "name": "RITA Sala Ana",    "location": "Sala",    "last_seen": None},
    {"user": "Demo :: Carlos López",  "code": "demo-device-carlos", "name": "RITA Sala Carlos", "location": "Sala",    "last_seen": 2},
    {"user": "Demo :: Carlos López",  "code": "demo-device-carlos-dormitorio", "name": "RITA Dormitorio Carlos", "location": "Dormitorio", "last_seen": 12},
    {"user": "Demo :: María Torres",  "code": "demo-device-maria",  "name": "RITA Sala María",  "location": "Cocina",  "last_seen": 60},
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_now = datetime.now(timezone.utc)


def _get_or_create_user(db: Session, full_name: str, notes: str) -> User:
    user = db.scalar(select(User).where(User.full_name == full_name))
    if user is None:
        user = User(full_name=full_name, notes=notes)
        db.add(user)
        db.flush()
        print(f"  [+] Usuario creado: {full_name}")
    else:
        print(f"  [=] Usuario existente: {full_name} (id={user.id})")
    return user


def _get_or_create_device(
    db: Session,
    user: User,
    code: str,
    name: str,
    location: str,
    last_seen_minutes_ago: int | None,
) -> Device:
    device = db.scalar(select(Device).where(Device.device_code == code))
    if device is None:
        last_seen = (
            _now - timedelta(minutes=last_seen_minutes_ago) if last_seen_minutes_ago is not None else None
        )
        device = Device(
            user_id=user.id,
            device_code=code,
            device_name=name,
            location_name=location,
            is_active=True,
            last_seen_at=last_seen,
        )
        db.add(device)
        db.flush()
        print(f"  [+] Dispositivo creado: {code}  (last_seen={last_seen_minutes_ago} min atrás)")
    else:
        print(f"  [=] Dispositivo existente: {code} (id={device.id})")
    return device


def _user_has_events(db: Session, user_id: int) -> bool:
    return db.scalar(select(Event).where(Event.user_id == user_id)) is not None


# ---------------------------------------------------------------------------
# Seed principal
# ---------------------------------------------------------------------------
def seed(db: Session) -> None:
    print("\n=== Seed demo — inicio ===")

    # Resolver usuarios
    users: dict[str, User] = {}
    for user_def in DEMO_USERS:
        users[user_def["full_name"]] = _get_or_create_user(
            db,
            user_def["full_name"],
            user_def["notes"],
        )

    # Resolver dispositivos
    devices: dict[str, Device] = {}
    for device_def in DEMO_DEVICES:
        user = users[device_def["user"]]
        device = _get_or_create_device(
            db,
            user,
            device_def["code"],
            device_def["name"],
            device_def["location"],
            device_def["last_seen"],
        )
        devices[device_def["code"]] = device

    db.commit()

    # --- Escenario 1: Ana — sin actividad (ningún evento) ------------------
    # No se crea nada más, ya que el escenario es "sin actividad".
    print("\n  Escenario Ana: sin actividad  → OK")

    # --- Escenario 2: Carlos — incidente abierto + alerta pendiente --------
    carlos = users["Demo :: Carlos López"]
    device_carlos = devices["demo-device-carlos"]

    if not _user_has_events(db, carlos.id):
        # Checkin reciente
        _create_direct_event(db, device_carlos, EventTypeEnum.checkin, SeverityEnum.low,
                              "Todo bien por aquí", minutes_ago=120)
        # Caída → genera incidente + alerta via servicio
        _create_via_service(db, device_carlos, EventTypeEnum.fall, SeverityEnum.high,
                            "Me he caído y no puedo levantarme", minutes_ago=30,
                            extra={"location": "Sala", "can_call": True})
        # Emergencia → genera otro incidente + alerta
        _create_via_service(db, device_carlos, EventTypeEnum.emergency, SeverityEnum.high,
                            "Emergency button pressed", minutes_ago=15,
                            extra={"location": "Dormitorio"})
        print("  Escenario Carlos: eventos + incidente + alerta  → creados")
    else:
        print("  Escenario Carlos: ya tiene eventos  → omitido")

    # --- Escenario 3: María — alertas pendientes, incidentes ya cerrados ---
    maria = users["Demo :: María Torres"]
    device_maria = devices["demo-device-maria"]

    if not _user_has_events(db, maria.id):
        # Caída → incidente+alerta (luego cerramos el incidente, dejamos alerta pending)
        _create_via_service(db, device_maria, EventTypeEnum.fall, SeverityEnum.medium,
                             "Me caí ayer pero estoy bien ahora", minutes_ago=1440,
                             extra={"location": "Cocina"})
        # Cierra el incidente manualmente
        incident = db.scalar(
            select(Incident)
            .where(Incident.user_id == maria.id, Incident.status == IncidentStatusEnum.open)
        )
        if incident:
            incident.status = IncidentStatusEnum.closed
            incident.closed_at = _now - timedelta(minutes=1400)
            db.flush()
        # Distress posterior → genera otro incidente+alerta, lo dejamos open
        _create_via_service(db, device_maria, EventTypeEnum.distress, SeverityEnum.medium,
                            "Auxilio", minutes_ago=200)
        db.commit()
        print("  Escenario María: incidente cerrado + alertas pendientes  → creados")
    else:
        print("  Escenario María: ya tiene eventos  → omitido")

    print("\n=== Seed demo — completado ===\n")


def _create_direct_event(
    db: Session,
    device: Device,
    event_type: EventTypeEnum,
    severity: SeverityEnum,
    user_text: str,
    minutes_ago: int,
) -> Event:
    event = Event(
        trace_id=str(uuid4()),
        user_id=device.user_id,
        device_id=device.id,
        event_type=event_type,
        severity=severity,
        source="seed-demo",
        user_text=user_text,
    )
    db.add(event)
    db.flush()
    # Ajustar created_at retroactivamente
    event.created_at = _now - timedelta(minutes=minutes_ago)
    db.flush()
    return event


def _create_via_service(
    db: Session,
    device: Device,
    event_type: EventTypeEnum,
    severity: SeverityEnum,
    user_text: str,
    minutes_ago: int,
    extra: dict | None = None,
) -> Event | None:
    payload = EventCreate(
        schema_version="1.0",
        trace_id=uuid4(),
        device_code=device.device_code,
        event_type=event_type,
        severity=severity,
        source="seed-demo",
        user_text=user_text,
        payload_json=extra or {},
    )
    event = create_event_with_side_effects(db, payload, device=device)
    if event:
        event.created_at = _now - timedelta(minutes=minutes_ago)
        db.commit()
    return event


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------
def reset_demo(db: Session) -> None:
    print("\n=== Reset demo — borrando datos demo ===")
    demo_names = [u["full_name"] for u in DEMO_USERS]
    demo_users = db.scalars(select(User).where(User.full_name.in_(demo_names))).all()
    for demo_user in demo_users:
        db.delete(demo_user)  # cascade borra devices, events, incidents, alerts
        print(f"  [-] Usuario eliminado: {demo_user.full_name}")
    db.commit()
    print("=== Reset demo — completado ===\n")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Seed de datos demo para RITA backend")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Borra los datos demo existentes antes de recrearlos",
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with session_factory() as db:
        if args.reset:
            reset_demo(db)
        seed(db)


if __name__ == "__main__":
    main()
