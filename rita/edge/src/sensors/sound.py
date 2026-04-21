from __future__ import annotations

import threading
import time
import logging
from typing import Callable, Optional

# Intentamos importar gpiozero
try:
    from gpiozero import DigitalInputDevice
    HAS_GPIO = True
except (ImportError, RuntimeError):
    HAS_GPIO = False
    logging.warning("gpiozero no detectado. Usando modo simulación para SoundSensor.")

logger = logging.getLogger(__name__)

class SoundSensor:
    """
    Controlador para el sensor de sonido (HW-484).
    Incluye un hilo de monitoreo de alta frecuencia y un filtro de confirmación
    para evitar falsos positivos por estática o interferencia Wi-Fi.
    """
    def __init__(self, pin: int = 18, on_noise_callback: Optional[Callable] = None):
        self.pin = pin
        self.on_noise_callback = on_noise_callback
        self.sensor = None
        self.noise_detected = False
        self._running = True
        
        if HAS_GPIO:
            try:
                # Usamos pull_up=False porque el HW-484 suele enviar señal en alto (1) al detectar sonido
                self.sensor = DigitalInputDevice(pin, pull_up=False)
                logger.info(f"Sensor de Sonido inicializado en el pin GPIO {pin}")
            except Exception as e:
                logger.error(f"Error al inicializar DigitalInputDevice en pin {pin}: {e}")
                self._running = False
        else:
            logger.info(f"[SIMULACIÓN] Sensor de Sonido inicializado virtualmente en pin {pin}")

        # Hilo de escaneo de alta frecuencia (20ms)
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="SoundMonitor")
        if self._running:
            self._thread.start()

    def _monitor_loop(self):
        """Bucle de monitoreo con filtro 'antifantasmas'."""
        logger.info("Hilo de monitoreo de sonido iniciado.")
        while self._running:
            if HAS_GPIO and self.sensor:
                if self.sensor.value == 1:
                    # [FILTRO ANTIFANTASMAS]: Confirmación tras 10ms
                    # Si lee 1, podría ser estática. Un golpe real tiene duración.
                    time.sleep(0.01)
                    if self.sensor.value == 1:
                        self._trigger_noise()
                        # Dormimos un poco para no registrar el mismo eco del golpe
                        time.sleep(0.5)
            
            time.sleep(0.02) # Frecuencia de muestreo ~50Hz

    def _trigger_noise(self):
        logger.info("¡Ruido/Golpe detectado genuinamente!")
        self.noise_detected = True
        if self.on_noise_callback:
            # Ejecutamos el callback en un hilo separado para no bloquear el monitor
            threading.Thread(target=self.on_noise_callback, daemon=True).start()

    def check_and_clear_noise(self) -> bool:
        """Devuelve True si hubo ruido desde la última vez y limpia el estado."""
        if self.noise_detected:
            self.noise_detected = False
            return True
        return False

    def cleanup(self):
        self._running = False
        if HAS_GPIO and self.sensor:
            self.sensor.close()
            logger.info("Sensor de Sonido liberado.")

if __name__ == "__main__":
    # Script de prueba rápida
    logging.basicConfig(level=logging.INFO)
    def mi_callback():
        print(">>> CALLBACK: El sistema ha sido notificado del ruido.")

    sound = SoundSensor(pin=18, on_noise_callback=mi_callback)
    try:
        print("Monitoreando sonido... (Ctrl+C para salir)")
        while True:
            if not HAS_GPIO:
                # Simulación manual para pruebas
                time.sleep(5)
                sound._trigger_noise()
            time.sleep(1)
    except KeyboardInterrupt:
        sound.cleanup()
