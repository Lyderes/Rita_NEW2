from __future__ import annotations

import wave
from datetime import datetime
from pathlib import Path
from threading import Event


class MicrophoneUnavailableError(RuntimeError):
    """Raised when no microphone device can be opened."""


class AudioRecorder:
    """One-shot recorder with RITA-style silence-based early stop."""

    def __init__(
        self,
        recordings_dir: Path,
        sample_rate: int = 16000,
        channels: int = 1,
        blocksize: int = 512,
        silence_amplitude: float = 0.02,
        prefix: str = "user",
    ) -> None:
        self.recordings_dir = recordings_dir
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.silence_amplitude = silence_amplitude
        self.prefix = prefix
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

    def record(self, max_duration_s: float = 10.0, silence_s: float = 1.5) -> Path:
        """Record to WAV and stop early when enough silence is detected."""
        import numpy as np
        import sounddevice as sd

        frames: list[object] = []
        silence_frames = 0
        total_frames = 0
        silence_limit = int(silence_s * self.sample_rate)
        max_frames = int(max_duration_s * self.sample_rate)
        stop_event = Event()

        def callback(indata: object, frame_count: int, _time: object, _status: object) -> None:
            nonlocal silence_frames, total_frames
            chunk = np.asarray(indata)
            frames.append(chunk.copy())
            total_frames += frame_count

            if float(np.max(np.abs(chunk))) < self.silence_amplitude:
                silence_frames += frame_count
            else:
                silence_frames = 0

            if silence_frames >= silence_limit or total_frames >= max_frames:
                stop_event.set()
                raise sd.CallbackStop()

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.blocksize,
                callback=callback,
            ):
                while not stop_event.wait(0.05):
                    pass
        except Exception as exc:
            if isinstance(exc, sd.CallbackStop):
                pass
            else:
                raise MicrophoneUnavailableError(
                    "No se pudo abrir el microfono. Revisa permisos y dispositivo de entrada."
                ) from exc

        if not frames:
            raise RuntimeError("No se capturo audio desde el microfono.")

        audio = np.concatenate(frames)
        pcm = (audio * 32767).astype(np.int16)
        output = self.recordings_dir / f"{self.prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        with wave.open(str(output), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm.tobytes())
        return output
