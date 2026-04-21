from __future__ import annotations

import json
import queue
import logging
from pathlib import Path
from typing import Generator, Optional

try:
    import sounddevice as sd
    from vosk import KaldiRecognizer, Model
    HAS_VOSK = True
except ImportError:
    HAS_VOSK = False
    logging.warning("Vosk o sounddevice no instalados. El modo escucha continua estará deshabilitado.")

logger = logging.getLogger(__name__)

class ContinuousSTT:
    """
    Motor de escucha continua usando Vosk.
    Transplantado de RITA_NEW para mantener la interactividad "Always Listening".
    """
    def __init__(self, model_path: Optional[Path] = None, sample_rate: Optional[int] = None):
        self.model = None
        self.q = queue.Queue()
        self.device_index = None
        self.sample_rate = sample_rate
        self.model_path = model_path
        self.needs_reset = False
        self._should_stop = False

        if HAS_VOSK:
            if self.model_path is None or not self.model_path.exists():
                # Intentar ruta por defecto
                base_dir = Path(__file__).resolve().parent.parent.parent.parent
                self.model_path = base_dir / "models" / "vosk-model-small-es-0.42"
            
            if self.model_path.exists():
                try:
                    self.model = Model(str(self.model_path))
                    self._find_input_device()
                    logger.info(f"Vosk cargado desde {self.model_path}")
                except Exception as e:
                    logger.error(f"Error cargando modelo Vosk: {e}")
            else:
                logger.warning(f"Modelo Vosk no encontrado en {self.model_path}")

    def _find_input_device(self):
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev["max_input_channels"] >= 1:
                    self.device_index = i
                    if self.sample_rate is None:
                        self.sample_rate = int(dev["default_samplerate"])
                    logger.info(f"Micrófono detectado: {dev['name']} (Sample Rate: {self.sample_rate})")
                    return
            logger.warning("No se encontró ningún micrófono con canales de entrada.")
        except Exception as e:
            logger.error(f"Error al consultar dispositivos de audio: {e}")

    def _callback(self, indata, frames, time, status):
        if status:
            logger.debug(f"Audio status: {status}")
        if not getattr(self, 'paused', False):
            self.q.put(bytes(indata))

    def clear_buffer(self):
        """Vacía la cola para no procesar audio antiguo."""
        with self.q.mutex:
            self.q.queue.clear()
        self.needs_reset = True

    def pause(self):
        self.paused = True
        self.clear_buffer()

    def resume(self):
        self.clear_buffer()
        self.paused = False

    def listen(self) -> Generator[Optional[str], None, None]:
        """Generador que produce texto transcrito de forma continua."""
        if not self.model or self.device_index is None:
            logger.error("No se puede iniciar escucha: Vosk no inicializado o micro no encontrado.")
            return

        recognizer = KaldiRecognizer(self.model, self.sample_rate)
        
        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=8000,
                device=self.device_index,
                dtype="int16",
                channels=1,
                callback=self._callback
            ):
                logger.info("🎤 Escucha continua activada...")
                while not self._should_stop:
                    if self.needs_reset:
                        recognizer.Reset()
                        self.needs_reset = False

                    try:
                        data = self.q.get(timeout=0.1)
                    except queue.Empty:
                        yield None
                        continue

                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").strip()
                        if text:
                            yield text
                    else:
                        # Resultados parciales si se desea (opcional)
                        pass
        except Exception as e:
            logger.error(f"Error en el stream de audio: {e}")

    def stop(self):
        self._should_stop = True

if __name__ == "__main__":
    # Prueba rápida
    logging.basicConfig(level=logging.INFO)
    stt = ContinuousSTT()
    try:
        for text in stt.listen():
            if text:
                print(f"Escuchado: {text}")
    except KeyboardInterrupt:
        stt.stop()
