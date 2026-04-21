from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np

from src.audio.recorder import AudioRecorder


class _FakeInputStream:
    def __init__(self, *, samplerate, channels, blocksize, callback):
        self.callback = callback
        self.blocksize = blocksize

    def __enter__(self):
        loud = np.ones((self.blocksize, 1), dtype=np.float32) * 0.5
        silent = np.zeros((self.blocksize, 1), dtype=np.float32)

        self.callback(loud, self.blocksize, None, None)
        self.callback(silent, self.blocksize, None, None)
        self.callback(silent, self.blocksize, None, None)
        return self

    def __exit__(self, exc_type, exc, _tb):
        return exc_type is _FakeSoundDevice.CallbackStop


class _FakeSoundDevice(types.SimpleNamespace):
    class CallbackStop(Exception):
        pass

    InputStream = _FakeInputStream


def test_record_stops_without_sleep(monkeypatch, tmp_path: Path) -> None:
    called = {"sleep": False}

    def _fake_sleep(_ms: int) -> None:
        called["sleep"] = True
        raise AssertionError("record() no debe depender de sd.sleep()")

    fake_sd = _FakeSoundDevice(sleep=_fake_sleep)
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    recorder = AudioRecorder(
        recordings_dir=tmp_path,
        sample_rate=4,
        channels=1,
        blocksize=2,
        silence_amplitude=0.02,
    )

    wav_path = recorder.record(max_duration_s=2.0, silence_s=1.0)

    assert wav_path.exists() is True
    assert called["sleep"] is False
