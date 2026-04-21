from __future__ import annotations
import logging, os, sys, time, requests
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("RitaEdge")

from src.config import load_config
from src.sensors.pir import PirSensor
from src.sensors.sound import SoundSensor
from src.stt.continuous_stt import ContinuousSTT
from src.tts.engine import TtsEngine
from src.integrations.mqtt_client import RitaMqttClient

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")
except: pass

class RitaEdgeAssistant:
    def __init__(self):
        self.config = load_config()
        self.mqtt = RitaMqttClient(
            host=os.getenv("MQTT_HOST", "10.7.21.13"),
            port=int(os.getenv("MQTT_PORT", "1883")),
            topics_to_subscribe=["rita/commands/speak"],
            buffer_path=Path(__file__).resolve().parent.parent / "mqtt_buffer.jsonl"
        )
        self.tts = TtsEngine(model_path=Path(self.config.stt_model_path).parent / "es_ES-carlfm-x_low.onnx")
        self.stt = ContinuousSTT(model_path=Path(self.config.stt_model_path))
        self.pir = PirSensor(pin=self.config.pir_gpio_pin, on_motion_callback=self._on_motion)
        self.sound = SoundSensor(pin=self.config.sound_gpio_pin, on_noise_callback=self._on_noise)
        self.modo_conversacion, self.modo_emergencia, self._should_exit = False, 0, False
        self.mqtt.register_callback("rita/commands/speak", self._mqtt_on_speak)

    def _update_ui(self, status="esperando", user="", rita=""):
        try: requests.post("http://localhost:5000/api/update", json={"status": status, "user_text": user, "rita_text": rita}, timeout=0.1)
        except: pass

    def _mqtt_on_speak(self, data):
        text = data.get("text", "") if isinstance(data, dict) else data
        if text:
            self._update_ui(status="hablando", rita=text)
            self.stt.pause()
            self.tts.speak(text)
            self.stt.resume()
            self._update_ui(status="esperando")

    def _on_motion(self):
        self.mqtt.publish("rita/events/motion", {"event_type": "possible_fall", "device_code": self.config.backend_device_code})

    def _on_noise(self):
        self.mqtt.publish("rita/events/noise", {"event_type": "health_concern", "device_code": self.config.backend_device_code})

    def run(self):
        self.mqtt.connect()
        self._update_ui(status="esperando")
        try:
            for text in self.stt.listen():
                if self._should_exit: break
                self._update_ui(status="escuchando")
                if text:
                    t = text.lower()
                    self._update_ui(status="pensando", user=text)
                    if not self.modo_conversacion:
                        if any(w in t for w in ["rita", "ayuda", "hola"]):
                            self.modo_conversacion = True
                            self.stt.pause()
                            self.tts.speak("Dime, te escucho.")
                            self.stt.resume()
                            self._update_ui(status="esperando", user="¿Dime?")
                        continue
                    if any(w in t for w in ["adiós", "adios", "salir"]):
                        self.stt.pause()
                        self.tts.speak("Hasta luego.")
                        self.stt.resume()
                        self.modo_conversacion = False
                        self._update_ui(status="esperando", user="")
                        continue
                    self.mqtt.publish("rita/events/speech", {"event_type": "user_speech", "user_text": text, "device_code": self.config.backend_device_code})
                    if not self.mqtt.is_connected():
                        self.stt.pause()
                        self.tts.speak("Sin conexión, lo he guardado.")
                        self.stt.resume()
                else:
                    self._update_ui(status="esperando")
        finally: self.cleanup()

    def cleanup(self):
        self.pir.cleanup(); self.sound.cleanup(); self.mqtt.disconnect()

if __name__ == "__main__":
    RitaEdgeAssistant().run()
