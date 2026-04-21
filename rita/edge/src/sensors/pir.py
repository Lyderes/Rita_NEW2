from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Callable, Optional

# Intentamos importar gpiozero, si falla (porque no estamos en una Pi), usamos un mock para desarrollo
try:
    from gpiozero import MotionSensor
    HAS_GPIO = True
except (ImportError, RuntimeError):
    HAS_GPIO = False
    logging.warning("gpiozero no detectado. Usando modo simulación para PirSensor.")

logger = logging.getLogger(__name__)

class PirSensor:
    """
    Controlador para el sensor de movimiento PIR.
    Transplantado de RITA_NEW con mejoras de portabilidad y callbacks.
    """
    def __init__(self, pin: int = 17, on_motion_callback: Optional[Callable] = None):
        self.pin = pin
        self.on_motion_callback = on_motion_callback
        self.sensor = None
        
        if HAS_GPIO:
            try:
                self.sensor = MotionSensor(pin)
                self.sensor.when_motion = self._internal_callback
                logger.info(f"Sensor PIR inicializado en el pin GPIO {pin}")
            except Exception as e:
                logger.error(f"Error al inicializar MotionSensor en pin {pin}: {e}")
        else:
            logger.info(f"[SIMULACIÓN] Sensor PIR inicializado virtualmente en pin {pin}")

    def _internal_callback(self):
        logger.info("¡Movimiento detectado por el sensor PIR!")
        if self.on_motion_callback:
            self.on_motion_callback()

    def wait_for_motion(self, timeout: Optional[float] = None):
        """Bloquea hasta detectar movimiento (solo para scripts de prueba)."""
        if HAS_GPIO and self.sensor:
            return self.sensor.wait_for_motion(timeout)
        else:
            time.sleep(2)
            logger.info("[SIMULACIÓN] Simulando detección de movimiento tras 2s")
            self._internal_callback()
            return True

    def is_active(self) -> bool:
        """Devuelve True si hay movimiento en este momento."""
        if HAS_GPIO and self.sensor:
            return self.sensor.motion_detected
        return False

    def cleanup(self):
        if HAS_GPIO and self.sensor:
            self.sensor.close()
            logger.info("Sensor PIR liberado.")

if __name__ == "__main__":
    # Script de prueba rápida
    logging.basicConfig(level=logging.INFO)
    def mi_callback():
        print(">>> CALLBACK: El sistema ha sido notificado del movimiento.")

    pir = PirSensor(pin=17, on_motion_callback=mi_callback)
    try:
        print("Esperando movimiento... (Ctrl+C para salir)")
        while True:
            pir.wait_for_motion()
            time.sleep(1)
    except KeyboardInterrupt:
        pir.cleanup()
