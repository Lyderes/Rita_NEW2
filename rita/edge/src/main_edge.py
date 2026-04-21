from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RitaEdge")

from src.config import load_config
from src.sensors.pir import PirSensor
from src.sensors.sound import SoundSensor
from src.stt.continuous_stt import ContinuousSTT
from src.tts.engine import TtsEngine
from src.integrations.mqtt_client import RitaMqttClient

# Cargar variables de entorno desde .env si existe
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

class RitaEdgeAssistant:
    def __init__(self):
        self.config = load_config()
        self.mqtt = RitaMqttClient(
            host=os.getenv("MQTT_HOST", "10.7.21.13"),
            port=int(os.getenv("MQTT_PORT", "1883")),
            topics_to_subscribe=["rita/commands/speak", "rita/commands/exit"],
            buffer_path=Path(__file__).resolve().parent.parent / "mqtt_buffer.jsonl"
        )
        
        self.tts = TtsEngine(
            model_path=Path(self.config.stt_model_path).parent / "es_ES-carlfm-x_low.onnx"
        )
        self.stt = ContinuousSTT(
            model_path=Path(self.config.stt_model_path)
        )
        
        self.pir = PirSensor(
            pin=self.config.pir_gpio_pin,
            on_motion_callback=self._on_motion
        )
        self.sound = SoundSensor(
            pin=self.config.sound_gpio_pin,
            on_noise_callback=self._on_noise
        )
        
        self.modo_conversacion = False
        self.modo_emergencia = 0 # 0: normal, 1: preguntando, 2: insistiendo
        self.tiempo_emergencia = 0
        self.last_checkin_hour = -1
        self._should_exit = False

        # Registrar callbacks de MQTT
        self.mqtt.register_callback("rita/commands/speak", self._mqtt_on_speak)
        self.mqtt.register_callback("rita/commands/exit", self._mqtt_on_exit)

    def _mqtt_on_speak(self, data):
        text = data.get("text", "") if isinstance(data, dict) else data
        if text:
            logger.info(f"Comando MQTT recibido: Hablar '{text}'")
            self.tts.speak(text)

    def _mqtt_on_exit(self, data):
        logger.info("Comando MQTT recibido: Salir")
        self._should_exit = True

    def _on_motion(self):
        # Publicar evento de movimiento
        self.mqtt.publish("rita/events/motion", {
            "timestamp": datetime.now().isoformat(),
            "device_code": self.config.backend_device_code
        })

    def _on_noise(self):
        # Publicar evento de ruido
        self.mqtt.publish("rita/events/noise", {
            "timestamp": datetime.now().isoformat(),
            "device_code": self.config.backend_device_code,
            "severity": "high"
        })

    def run(self):
        logger.info("Iniciando Rita Edge Assistant...")
        self.mqtt.connect()
        
        print("\n--- RITA EDGE UNIFIED ---")
        print("Modo Siempre Escuchando activo.")
        print("MQTT Conectado. Sensores Armados.\n")

        try:
            for text in self.stt.listen():
                if self._should_exit:
                    break
                
                current_time = time.time()
                current_hour = datetime.now().hour
                
                # A. Lógica Horaria PIR (Check-in)
                if not self.modo_conversacion and self.modo_emergencia == 0:
                    if current_hour in [9, 12, 17, 21] and current_hour != self.last_checkin_hour:
                        if self.pir.is_active():
                            self.last_checkin_hour = current_hour
                            self.modo_conversacion = True
                            msg = "Hola, he notado que estás por aquí. ¿Qué tal te encuentras?"
                            self.tts.speak(msg)
                            self.stt.clear_buffer()
                            continue

                # B. Protocolo de Caídas (Ruido + No movimiento)
                if not self.modo_conversacion and self.modo_emergencia == 0:
                    if self.sound.check_and_clear_noise():
                        logger.warning("¡Golpe detectado! Evaluando posible caída...")
                        time.sleep(3) # Pausa dramática para evaluar movimiento posterior
                        if not self.pir.is_active():
                            logger.error("No se detecta movimiento tras el golpe. Iniciando emergencia.")
                            self.modo_emergencia = 1
                            self.tiempo_emergencia = current_time
                            msg = "He escuchado un ruido fuerte. ¿Estás bien? Por favor, dime algo."
                            self.tts.speak(msg)
                            self.stt.clear_buffer()
                            continue

                # C. Procesamiento de Voz
                if text:
                    t = text.lower()
                    logger.info(f"Usuario: {text}")
                    
                    # C.1. Resolución de Emergencia por voz
                    if self.modo_emergencia > 0:
                        logger.info("Voz detectada durante emergencia. Abortando protocolo.")
                        self.modo_emergencia = 0
                        self.tts.speak("Entendido, me alegra que estés bien. Vuelvo a mi sitio.")
                        self.stt.clear_buffer()
                        continue
                    
                    # C.2. Wake-Word
                    if not self.modo_conversacion:
                        if any(word in t for word in ["rita", "ayuda", "hola"]):
                            self.modo_conversacion = True
                            self.tts.speak("Dime, te escucho.")
                            self.stt.clear_buffer()
                        continue
                    
                    # C.3. Conversación activa (Enviar al Backend)
                    if self.modo_conversacion:
                        if any(word in t for word in ["adiós", "adios", "salir", "terminar"]):
                            self.tts.speak("Hasta luego, cuídate.")
                            self.modo_conversacion = False
                            self.stt.clear_buffer()
                            continue
                        
                        # Publicar evento de habla para que el backend procese
                        logger.info("Enviando transcripción al backend por MQTT...")
                        sent = self.mqtt.publish("rita/events/speech", {
                            "text": text,
                            "device_code": self.config.backend_device_code,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        if not self.mqtt.is_connected():
                            # Respuesta local si estamos en modo PI (Offline)
                            logger.info("Modo PI activo: Respondiendo localmente.")
                            self.tts.speak("He anotado lo que me dices, pero ahora mismo no puedo conectar con el sistema central. Te responderé en cuanto recupere la conexión.")
                        
                        self.stt.clear_buffer()

                # D. Timeouts de Emergencia
                if self.modo_emergencia == 1 and (current_time - self.tiempo_emergencia) > 15:
                    self.modo_emergencia = 2
                    self.tiempo_emergencia = current_time
                    self.tts.speak("¿Sigues ahí? Por favor, dime algo si me oyes.")
                    self.stt.clear_buffer()
                
                elif self.modo_emergencia == 2 and (current_time - self.tiempo_emergencia) > 15:
                    logger.critical("ALARMA CRÍTICA: Notificando a familiares.")
                    self.mqtt.publish("rita/events/alarm", {
                        "type": "fall_detected",
                        "severity": "critical",
                        "device_code": self.config.backend_device_code
                    })
                    self.tts.speak("No recibo respuesta. He enviado un aviso de emergencia a tus familiares. Mantén la calma.")
                    self.modo_emergencia = 0
                    self.modo_conversacion = False

        except KeyboardInterrupt:
            logger.info("Cerrando por interrupción de usuario...")
        finally:
            self.cleanup()

    def cleanup(self):
        self.pir.cleanup()
        self.sound.cleanup()
        self.mqtt.disconnect()
        logger.info("Limpieza completada. Rita apagada.")

if __name__ == "__main__":
    assistant = RitaEdgeAssistant()
    assistant.run()
