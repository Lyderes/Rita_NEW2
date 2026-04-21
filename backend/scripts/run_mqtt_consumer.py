from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.services.mqtt_ingest_service import MqttEventIngestor  # noqa: E402

try:
    import paho.mqtt.client as mqtt
except Exception as exc:  # pragma: no cover - validated by manual run
    raise SystemExit(
        "Missing dependency 'paho-mqtt'. Install backend requirements before running this script."
    ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MQTT consumer and ingest events into backend DB")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.getenv("MQTT_USERNAME"))
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD"))
    parser.add_argument(
        "--topics",
        default=os.getenv("MQTT_TOPICS", "rita/events/#"),
        help="Comma-separated MQTT topics",
    )
    parser.add_argument("--qos", type=int, default=int(os.getenv("MQTT_QOS", "1")))
    parser.add_argument("--client-id", default=os.getenv("MQTT_CLIENT_ID", "rita-backend-consumer"))
    parser.add_argument("--keepalive", type=int, default=int(os.getenv("MQTT_KEEPALIVE", "30")))
    return parser


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def main() -> int:
    args = _build_parser().parse_args()
    topics = [topic.strip() for topic in args.topics.split(",") if topic.strip()]
    if not topics:
        print("No MQTT topics configured")
        return 2

    ingestor = MqttEventIngestor(session_factory=SessionLocal)
    client = mqtt.Client(client_id=args.client_id, protocol=mqtt.MQTTv311)
    if args.username:
        client.username_pw_set(args.username, args.password)

    def on_connect(client: mqtt.Client, _userdata, _flags, rc: int):
        if rc != 0:
            print(f"[{_now_iso()}] mqtt connect failed rc={rc}")
            return
        print(f"[{_now_iso()}] mqtt connected host={args.host}:{args.port}")
        for topic in topics:
            client.subscribe(topic, qos=args.qos)
            print(f"[{_now_iso()}] subscribed topic={topic} qos={args.qos}")

    def on_message(_client: mqtt.Client, _userdata, msg: mqtt.MQTTMessage):
        result = ingestor.process_message(topic=msg.topic, payload_bytes=msg.payload)
        line = {
            "ts": _now_iso(),
            "topic": msg.topic,
            "status": result.status.value,
            "detail": result.detail,
            "trace_id": result.trace_id,
            "event_id": result.event_id,
        }
        print(json.dumps(line, ensure_ascii=True))

    client.on_connect = on_connect
    client.on_message = on_message

    stop_requested = {"value": False}

    def _request_stop(_signum, _frame):
        stop_requested["value"] = True

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    client.connect(args.host, args.port, keepalive=args.keepalive)
    client.loop_start()
    try:
        while not stop_requested["value"]:
            time.sleep(0.25)
    finally:
        client.loop_stop()
        client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
