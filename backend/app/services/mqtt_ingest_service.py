from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.event import Event
from app.schemas.event import EventCreate
from app.services.event_service import (
    EventSemanticValidationError,
    TraceIdConflictError,
    UnsupportedEventTypeError,
    create_event_with_side_effects,
)
import logging
import os

logger = logging.getLogger(__name__)

_MQTT_TRACE_NAMESPACE = UUID("5c63288f-a5e9-47f0-a24b-f7e632e9fcf2")


class MqttIngestStatus(str, Enum):
    created = "created"
    idempotent = "idempotent"
    unknown_device = "unknown_device"
    invalid_payload = "invalid_payload"
    unsupported_event_type = "unsupported_event_type"
    semantic_error = "semantic_error"
    trace_conflict = "trace_conflict"
    processing_error = "processing_error"


@dataclass(slots=True)
class MqttIngestResult:
    status: MqttIngestStatus
    detail: str
    trace_id: str | None = None
    event_id: int | None = None


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _derive_trace_id(*, topic: str, message_obj: dict[str, Any]) -> str:
    key = f"mqtt:{topic}:{_stable_json(message_obj)}"
    return str(uuid5(_MQTT_TRACE_NAMESPACE, key))


def _extract_payload_json(message_obj: dict[str, Any]) -> dict[str, Any] | None:
    explicit_payload = message_obj.get("payload_json")
    if isinstance(explicit_payload, dict):
        return explicit_payload

    reserved_keys = {
        "schema_version",
        "trace_id",
        "device_code",
        "event_type",
        "severity",
        "source",
        "user_text",
        "rita_text",
        "payload_json",
    }
    extra_payload = {k: v for k, v in message_obj.items() if k not in reserved_keys}
    return extra_payload or None


def _build_event_create_from_mqtt(*, topic: str, payload_bytes: bytes) -> EventCreate:
    decoded = payload_bytes.decode("utf-8")
    raw = json.loads(decoded)
    if not isinstance(raw, dict):
        raise ValueError("MQTT payload must be a JSON object")

    trace = raw.get("trace_id")
    if not isinstance(trace, str) or not trace.strip():
        trace = _derive_trace_id(topic=topic, message_obj=raw)

    event_raw: dict[str, Any] = {
        "schema_version": raw.get("schema_version", "1.0"),
        "trace_id": trace,
        "device_code": raw.get("device_code"),
        "event_type": raw.get("event_type"),
        "severity": raw.get("severity"),
        "source": raw.get("source") or f"mqtt:{topic}",
        "user_text": raw.get("user_text"),
        "rita_text": raw.get("rita_text"),
        "payload_json": _extract_payload_json(raw),
    }
    return EventCreate.model_validate(event_raw)


class MqttEventIngestor:
    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def process_message(self, *, topic: str, payload_bytes: bytes) -> MqttIngestResult:
        try:
            event_payload = _build_event_create_from_mqtt(topic=topic, payload_bytes=payload_bytes)
        except Exception as exc:
            return MqttIngestResult(
                status=MqttIngestStatus.invalid_payload,
                detail=f"invalid mqtt payload: {exc}",
            )

        db = self._session_factory()
        try:
            existing = db.scalar(select(Event.id).where(Event.trace_id == str(event_payload.trace_id)))

            try:
                event = create_event_with_side_effects(db, event_payload)
            except UnsupportedEventTypeError as exc:
                return MqttIngestResult(
                    status=MqttIngestStatus.unsupported_event_type,
                    detail=str(exc),
                    trace_id=str(event_payload.trace_id),
                )
            except EventSemanticValidationError as exc:
                return MqttIngestResult(
                    status=MqttIngestStatus.semantic_error,
                    detail=str(exc),
                    trace_id=str(event_payload.trace_id),
                )
            except TraceIdConflictError as exc:
                return MqttIngestResult(
                    status=MqttIngestStatus.trace_conflict,
                    detail=str(exc),
                    trace_id=str(event_payload.trace_id),
                )
            except Exception as exc:
                db.rollback()
                return MqttIngestResult(
                    status=MqttIngestStatus.processing_error,
                    detail=f"unexpected mqtt processing error: {exc}",
                    trace_id=str(event_payload.trace_id),
                )

            if event is None:
                return MqttIngestResult(
                    status=MqttIngestStatus.unknown_device,
                    detail="device not found",
                    trace_id=str(event_payload.trace_id),
                )

            # --- Bridge MQTT user_speech → ConversationService ---
            # Si es habla del usuario, procesamos la respuesta de la IA
            if (
                event.event_type.value == "user_speech"
                and event.user_text
                and existing is None
            ):
                self._handle_async_conversation(event)

            if existing is not None:
                return MqttIngestResult(
                    status=MqttIngestStatus.idempotent,
                    detail="trace_id already processed",
                    trace_id=event.trace_id,
                    event_id=event.id,
                )

            return MqttIngestResult(
                status=MqttIngestStatus.created,
                detail="event created",
                trace_id=event.trace_id,
                event_id=event.id,
            )
        finally:
            db.close()

    def _handle_async_conversation(self, event: Event):
        """Procesa la conversación en segundo plano y publica la respuesta en MQTT."""
        import threading
        
        def _run():
            import asyncio
            from app.db.session import SessionLocal
            from app.api.events import _handle_user_speech
            from app.core.config import get_settings
            import paho.mqtt.client as mqtt

            db = SessionLocal()
            try:
                # 1. Obtener respuesta de la IA
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # Refrescamos el objeto event en esta sesión
                db_event = db.get(Event, event.id)
                if not db_event:
                    return
                
                loop.run_until_complete(_handle_user_speech(db, event=db_event, user_id=db_event.user_id))
                rita_text = db_event.rita_text
                loop.close()

                if rita_text:
                    # 2. Publicar respuesta en MQTT para que el Edge la diga
                    host = os.getenv("MQTT_HOST", "mqtt")
                    port = int(os.getenv("MQTT_PORT", "1883"))
                    client = mqtt.Client(client_id="rita-backend-responder")
                    
                    username = os.getenv("MQTT_USERNAME")
                    password = os.getenv("MQTT_PASSWORD")
                    if username:
                        client.username_pw_set(username, password)
                        
                    client.connect(host, port)
                    payload = json.dumps({"text": rita_text, "event_id": event.id})
                    client.publish("rita/commands/speak", payload, qos=1)
                    client.disconnect()
                    logger.info(f"Respuesta de Rita enviada por MQTT: {rita_text[:50]}...")
            except Exception as e:
                logger.error(f"Error procesando respuesta asíncrona MQTT: {e}")
            finally:
                db.close()

        threading.Thread(target=_run, daemon=True).start()
