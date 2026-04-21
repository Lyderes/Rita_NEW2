from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False
    logging.warning("paho-mqtt no instalado. El cliente MQTT del Edge estará deshabilitado.")

logger = logging.getLogger(__name__)

class RitaMqttClient:
    """
    Cliente MQTT para el componente Edge de RITA.
    Gestiona la comunicación asíncrona con el Backend.
    """
    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        client_id: str = "rita-edge-device",
        username: Optional[str] = None,
        password: Optional[str] = None,
        topics_to_subscribe: Optional[list[str]] = None,
        buffer_path: Optional[Path] = None
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.topics = topics_to_subscribe or []
        self.callbacks: Dict[str, Callable] = {}
        self.client: Optional[mqtt.Client] = None
        self._connected = False
        self.buffer_path = buffer_path or Path("mqtt_buffer.jsonl")

        if HAS_MQTT:
            self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
            if username:
                self.client.username_pw_set(username, password)
            
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect

    def connect(self):
        """Conecta al broker de forma no bloqueante."""
        if not HAS_MQTT or not self.client:
            return
        
        try:
            logger.info(f"Intentando conectar a MQTT en {self.host}:{self.port}...")
            # Intentamos conectar. Si falla, el loop_start se encargará de reintentar
            self.client.connect_async(self.host, self.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Error al iniciar conexión MQTT: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Conexión establecida con el Docker Central.")
            self._connected = True
            for topic in self.topics:
                client.subscribe(topic)
            self._flush_buffer()
        else:
            logger.error(f"Fallo de conexión MQTT: código {rc}")

    def _on_disconnect(self, client, userdata, rc):
        logger.warning("Se ha perdido la conexión con el Docker Central. Entrando en modo 'PI' (Offline).")
        self._connected = False

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode()
        if topic in self.callbacks:
            try:
                data = json.loads(payload)
                self.callbacks[topic](data)
            except Exception as e:
                logger.error(f"Error en callback MQTT: {e}")

    def register_callback(self, topic: str, callback: Callable):
        self.callbacks[topic] = callback
        if self._connected and self.client:
            self.client.subscribe(topic)

    def is_connected(self) -> bool:
        return self._connected

    def publish(self, topic: str, payload: Any, qos: int = 1):
        """Publica o guarda en el buffer si no hay conexión."""
        msg_dict = {
            "topic": topic,
            "payload": payload,
            "qos": qos,
            "timestamp": time.time()
        }

        if self._connected and self.client:
            try:
                msg = json.dumps(payload) if isinstance(payload, dict) else str(payload)
                self.client.publish(topic, msg, qos=qos)
                return True
            except Exception as e:
                logger.error(f"Error al publicar: {e}")
        
        # Si no está conectado o falla la publicación, guardamos en la "caja negra"
        self._add_to_buffer(msg_dict)
        return False

    def _add_to_buffer(self, msg_dict: dict):
        logger.info(f"Modo PI: Guardando evento en buffer local ({msg_dict['topic']})")
        try:
            with open(self.buffer_path, "a") as f:
                f.write(json.dumps(msg_dict) + "\n")
        except Exception as e:
            logger.error(f"Error al escribir en buffer: {e}")

    def _flush_buffer(self):
        """Envía los mensajes acumulados al reconectarse."""
        if not self.buffer_path.exists():
            return

        logger.info("Reconexión detectada: Sincronizando datos acumulados con el Docker Central...")
        try:
            remaining = []
            with open(self.buffer_path, "r") as f:
                for line in f:
                    if not line.strip(): continue
                    msg = json.loads(line)
                    # Intentamos publicar de nuevo
                    success = self.publish(msg["topic"], msg["payload"], msg["qos"])
                    if not success:
                        remaining.append(msg)
            
            # Limpiar archivo y reescribir solo los fallidos si los hay
            self.buffer_path.unlink()
            if remaining:
                for msg in remaining:
                    self._add_to_buffer(msg)
            else:
                logger.info("Sincronización completada con éxito.")
        except Exception as e:
            logger.error(f"Error al sincronizar buffer: {e}")

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    # Prueba rápida
    logging.basicConfig(level=logging.INFO)
    client = RitaMqttClient(topics_to_subscribe=["rita/commands/speak"])
    
    def on_speak(data):
        text = data.get("text", "") if isinstance(data, dict) else data
        print(f">>> COMANDO RECIBIDO: Rita debe decir: {text}")

    client.register_callback("rita/commands/speak", on_speak)
    client.connect()
    
    try:
        while True:
            client.publish("rita/events/heartbeat", {"status": "alive", "time": time.time()})
            time.sleep(10)
    except KeyboardInterrupt:
        client.disconnect()
