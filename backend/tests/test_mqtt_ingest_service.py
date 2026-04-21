import json
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.alert import Alert
from app.models.event import Event
from app.models.incident import Incident
from app.models.user import User
from app.models.device import Device
from app.services.mqtt_ingest_service import MqttIngestStatus, MqttEventIngestor


def _session_factory_for_tests():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal


def _seed_user_and_device(test_session_factory):
    db = test_session_factory()
    try:
        user = User(
            full_name="Test User",
        )
        db.add(user)
        db.flush()

        device = Device(
            device_code="dev-mqtt-1",
            device_name="Device MQTT 1",
            user_id=user.id,
            device_token_hash="hash",
            token_rotated_at=datetime.now(timezone.utc),
        )
        db.add(device)
        db.commit()
    finally:
        db.close()


def test_mqtt_ingest_created_then_idempotent_with_explicit_trace_id():
    session_factory = _session_factory_for_tests()
    _seed_user_and_device(session_factory)
    ingestor = MqttEventIngestor(session_factory=session_factory)

    payload = {
        "trace_id": "3f0ae6bf-55cb-4fc2-b47e-122e34d7b0fb",
        "device_code": "dev-mqtt-1",
        "event_type": "device_offline",
        "severity": "high",
        "source": "mqtt:test",
    }
    payload_bytes = json.dumps(payload).encode("utf-8")

    first = ingestor.process_message(topic="rita/events/dev-mqtt-1", payload_bytes=payload_bytes)
    second = ingestor.process_message(topic="rita/events/dev-mqtt-1", payload_bytes=payload_bytes)

    assert first.status == MqttIngestStatus.created
    assert second.status == MqttIngestStatus.idempotent

    db = session_factory()
    try:
        assert db.query(Event).count() == 1
        assert db.query(Incident).count() == 1
        assert db.query(Alert).count() == 1
    finally:
        db.close()


def test_mqtt_ingest_generates_deterministic_trace_id_for_duplicates():
    session_factory = _session_factory_for_tests()
    _seed_user_and_device(session_factory)
    ingestor = MqttEventIngestor(session_factory=session_factory)

    payload_without_trace = {
        "device_code": "dev-mqtt-1",
        "event_type": "device_offline",
        "severity": "high",
        "battery": 45,
    }
    payload_bytes = json.dumps(payload_without_trace).encode("utf-8")

    first = ingestor.process_message(topic="rita/events/dev-mqtt-1", payload_bytes=payload_bytes)
    second = ingestor.process_message(topic="rita/events/dev-mqtt-1", payload_bytes=payload_bytes)

    assert first.status == MqttIngestStatus.created
    assert second.status == MqttIngestStatus.idempotent
    assert first.trace_id is not None
    assert first.trace_id == second.trace_id
