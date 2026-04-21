from __future__ import annotations

import os
import subprocess
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class TtsError(RuntimeError):
    """Raised when local TTS engine fails."""

class TtsEngine:
    """
    Motor de voz basado en Piper TTS.
    Optimizado para Raspberry Pi con voces neuronales de alta calidad.
    Transplantado de RITA_NEW con mejoras de robustez y portabilidad.
    """

    def __init__(self, model_path: Optional[Path] = None, volume: float = 1.0) -> None:
        self.model_path = model_path
        self.volume = volume
        
        # Intentar localizar el modelo si no se proporciona
        if self.model_path is None:
            env_path = os.getenv("PIPER_MODEL_PATH")
            if env_path:
                self.model_path = Path(env_path)
            else:
                # Ruta por defecto relativa al proyecto
                base_dir = Path(__file__).resolve().parent.parent.parent.parent
                self.model_path = base_dir / "data" / "voices" / "es_ES-carlfm-x_low.onnx"
        
        # Archivo temporal para el audio generado
        self.output_file = Path(__file__).resolve().parent / "tts_out.wav"
        self.setup()

    def setup(self) -> None:
        """Verifica que Piper y el modelo estén disponibles."""
        if not self.model_path or not self.model_path.exists():
            logger.warning(f"[TTS] Modelo Piper no encontrado en {self.model_path}")
            # No lanzamos error aquí para permitir que el sistema inicie sin voz si es necesario
        else:
            logger.info(f"[TTS] Motor Piper listo con modelo: {self.model_path.name}")

    def speak(self, text: str) -> bool:
        """Sintetiza texto a voz y lo reproduce."""
        if not text.strip():
            return False

        logger.info(f"[TTS] Hablando: {text[:50]}...")
        
        # Limpiar texto de caracteres que Piper no maneja bien
        clean_text = re.sub(r'[^\w\s\.,;:!¡\?¿\-\'"]', '', text)

        try:
            # 1. Generar audio con Piper
            # Usamos el módulo piper de python si está instalado, o el ejecutable si no.
            # En la Raspberry Pi 5 configurada previamente, suele estar en el venv.
            
            # Buscamos el ejecutable de piper
            piper_cmd = ["piper", "--model", str(self.model_path), "--output_file", str(self.output_file)]
            
            # Si estamos en un venv, intentamos usar el python del venv para llamar al módulo
            venv_python = Path(os.sys.prefix) / "bin" / "python"
            if not venv_python.exists():
                venv_python = Path(os.sys.prefix) / "Scripts" / "python.exe" # Windows

            if venv_python.exists():
                cmd = [str(venv_python), "-m", "piper", "--model", str(self.model_path), "--output_file", str(self.output_file)]
            else:
                cmd = piper_cmd

            process = subprocess.run(
                cmd,
                input=clean_text,
                text=True,
                capture_output=True
            )

            if process.returncode != 0:
                logger.error(f"[TTS] Error en Piper: {process.stderr}")
                return False

            # 2. Reproducir el audio
            # En Linux usamos 'aplay', en Windows podríamos usar 'powershell -c (New-Object Media.SoundPlayer "...").PlaySync()'
            if os.name == 'posix':
                play_cmd = ["aplay", str(self.output_file)]
            else:
                # Mock para Windows
                logger.info(f"[SIMULACIÓN] Reproduciendo audio en Windows: {self.output_file}")
                return True

            subprocess.run(play_cmd, capture_output=True)
            return True

        except Exception as e:
            logger.error(f"[TTS] Error inesperado en el motor de voz: {e}")
            return False

if __name__ == "__main__":
    # Prueba rápida
    logging.basicConfig(level=logging.INFO)
    engine = TtsEngine()
    engine.speak("Hola, soy Rita. El sistema de voz está configurado correctamente.")
