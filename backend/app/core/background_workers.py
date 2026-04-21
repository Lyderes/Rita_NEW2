from __future__ import annotations

import logging
import os
import threading
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class MqttWorker:
    """Consumes RITA events from MQTT and ingests them into the database.

    Runs paho's network loop in a background thread.  The lifespan manager
    starts/stops this worker so no external script is needed.
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="mqtt-worker"
        )
        self._thread.start()
        logger.info("mqtt-worker started")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("mqtt-worker stopped")

    def _run(self) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("paho-mqtt not installed — mqtt-worker disabled")
            return

        from app.services.mqtt_ingest_service import MqttEventIngestor

        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", "1883"))
        raw_topics = os.getenv("MQTT_TOPICS", "rita/events/#")
        topics = [t.strip() for t in raw_topics.split(",") if t.strip()]

        ingestor = MqttEventIngestor(session_factory=self._session_factory)
        client = mqtt.Client(
            client_id="rita-backend-embedded", protocol=mqtt.MQTTv311
        )

        username = os.getenv("MQTT_USERNAME")
        password = os.getenv("MQTT_PASSWORD")
        if username:
            client.username_pw_set(username, password)

        def on_connect(client: mqtt.Client, _userdata, _flags, rc: int) -> None:
            if rc != 0:
                logger.error("mqtt connect failed rc=%s", rc)
                return
            logger.info("mqtt connected %s:%s", host, port)
            for topic in topics:
                client.subscribe(topic, qos=1)
                logger.info("mqtt subscribed topic=%s", topic)

        def on_message(
            _client: mqtt.Client, _userdata, msg: mqtt.MQTTMessage
        ) -> None:
            result = ingestor.process_message(
                topic=msg.topic, payload_bytes=msg.payload
            )
            logger.debug(
                "mqtt ingest topic=%s status=%s trace_id=%s",
                msg.topic,
                result.status.value,
                result.trace_id,
            )

        def on_disconnect(_client, _userdata, rc: int) -> None:
            if not self._stop_event.is_set():
                logger.warning("mqtt disconnected unexpectedly rc=%s", rc)

        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect

        try:
            client.connect(host, port, keepalive=30)
            client.loop_start()
            self._stop_event.wait()
        except Exception:
            logger.exception("mqtt-worker fatal error")
        finally:
            client.loop_stop()
            client.disconnect()


class NotificationWorker:
    """Polls pending NotificationJobs and dispatches them via FCM / Twilio / mock.

    Runs in a background thread.  The lifespan manager starts/stops this
    worker so no external script is needed.
    """

    def __init__(
        self,
        session_factory,
        interval_seconds: int = 60,
        batch_size: int = 100,
        base_backoff_seconds: int = 30,
    ) -> None:
        self._session_factory = session_factory
        self._interval_seconds = interval_seconds
        self._batch_size = batch_size
        self._base_backoff_seconds = base_backoff_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="notification-worker"
        )
        self._thread.start()
        logger.info(
            "notification-worker started interval=%ss batch_size=%s",
            self._interval_seconds,
            self._batch_size,
        )

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("notification-worker stopped")

    def _run(self) -> None:
        from app.services.notification_worker_service import run_notification_worker_once

        while not self._stop_event.is_set():
            db = self._session_factory()
            try:
                result = run_notification_worker_once(
                    db,
                    now=datetime.now(UTC),
                    batch_size=self._batch_size,
                    base_backoff_seconds=self._base_backoff_seconds,
                )
                if result.processed_jobs > 0:
                    logger.info(
                        "notification-worker cycle processed=%s sent=%s "
                        "rescheduled=%s failed=%s",
                        result.processed_jobs,
                        result.sent_jobs,
                        result.rescheduled_jobs,
                        result.terminal_failed_jobs,
                    )
            except Exception:
                logger.exception("notification-worker cycle error")
            finally:
                db.close()

            self._stop_event.wait(timeout=self._interval_seconds)


class DataRetentionWorker:
    """Purges old events, notification jobs, and closed alerts per GDPR retention policy.

    Runs once at startup and then every 24 hours.  Only active when
    settings.enable_data_retention is True; silently skips otherwise.
    """

    _INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="data-retention-worker"
        )
        self._thread.start()
        logger.info("data-retention-worker started interval=24h")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("data-retention-worker stopped")

    def _run(self) -> None:
        from app.core.config import get_settings
        from app.services.data_retention_service import run_data_retention

        while not self._stop_event.is_set():
            if get_settings().enable_data_retention:
                db = self._session_factory()
                try:
                    result = run_data_retention(db)
                    logger.info("data-retention-worker cycle result=%s", result)
                except Exception:
                    logger.exception("data-retention-worker cycle error")
                finally:
                    db.close()
            else:
                logger.debug("data-retention-worker skipped (ENABLE_DATA_RETENTION=false)")

            self._stop_event.wait(timeout=self._INTERVAL_SECONDS)


class AlertEscalationWorker:
    """Escalates pending alerts that exceed the pending threshold.

    Runs in a background thread.  The lifespan manager starts/stops this
    worker so no external script is needed.
    """

    def __init__(
        self,
        session_factory,
        interval_seconds: int = 60,
        pending_threshold_minutes: int = 10,
        source: str = "alert-escalation-monitor",
    ) -> None:
        self._session_factory = session_factory
        self._interval_seconds = interval_seconds
        self._pending_threshold_minutes = pending_threshold_minutes
        self._source = source
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="alert-escalation-worker"
        )
        self._thread.start()
        logger.info(
            "alert-escalation-worker started interval=%ss threshold=%sm",
            self._interval_seconds,
            self._pending_threshold_minutes,
        )

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("alert-escalation-worker stopped")

    def _run(self) -> None:
        from app.services.alert_escalation_service import run_alert_escalation_once

        while not self._stop_event.is_set():
            db = self._session_factory()
            try:
                result = run_alert_escalation_once(
                    db,
                    now=datetime.now(UTC),
                    pending_threshold_minutes=self._pending_threshold_minutes,
                    source=self._source,
                )
                if result.escalated_alerts > 0:
                    logger.info(
                        "alert-escalation-worker cycle escalated=%s jobs_created=%s",
                        result.escalated_alerts,
                        result.notification_jobs_created,
                    )
            except Exception:
                logger.exception("alert-escalation-worker cycle error")
            finally:
                db.close()

            self._stop_event.wait(timeout=self._interval_seconds)


class HeartbeatMonitorWorker:
    """Detects devices that have gone offline and creates device_offline events.

    Runs in a background thread.  The lifespan manager starts/stops this
    worker so no external script is needed.
    """

    def __init__(
        self,
        session_factory,
        interval_seconds: int = 60,
        offline_threshold_minutes: int = 30,
        no_heartbeat_grace_minutes: int = 30,
        source: str = "heartbeat-monitor",
    ) -> None:
        self._session_factory = session_factory
        self._interval_seconds = interval_seconds
        self._offline_threshold_minutes = offline_threshold_minutes
        self._no_heartbeat_grace_minutes = no_heartbeat_grace_minutes
        self._source = source
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="heartbeat-monitor-worker"
        )
        self._thread.start()
        logger.info(
            "heartbeat-monitor-worker started interval=%ss offline_threshold=%sm",
            self._interval_seconds,
            self._offline_threshold_minutes,
        )

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("heartbeat-monitor-worker stopped")

    def _run(self) -> None:
        from app.services.heartbeat_monitor_service import run_heartbeat_monitor_once

        while not self._stop_event.is_set():
            db = self._session_factory()
            try:
                result = run_heartbeat_monitor_once(
                    db,
                    now=datetime.now(UTC),
                    offline_threshold_minutes=self._offline_threshold_minutes,
                    no_heartbeat_grace_minutes=self._no_heartbeat_grace_minutes,
                    source=self._source,
                )
                if result.events_created > 0:
                    logger.info(
                        "heartbeat-monitor-worker cycle offline=%s events_created=%s",
                        result.offline_candidates,
                        result.events_created,
                    )
            except Exception:
                logger.exception("heartbeat-monitor-worker cycle error")
            finally:
                db.close()

            self._stop_event.wait(timeout=self._interval_seconds)
