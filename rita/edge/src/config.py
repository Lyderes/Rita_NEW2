from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[4] / "models" / "vosk-model-small-es-0.42"
DEFAULT_RECORDINGS_PATH = Path(__file__).resolve().parents[2] / "recordings"
DEFAULT_BACKEND_QUEUE_PATH = Path(__file__).resolve().parents[2] / "recordings" / "backend_events_queue.jsonl"
DEFAULT_BACKEND_BASE_URL = "http://localhost:8080"
DEFAULT_LLM_BASE_URL = "http://localhost:8001"


@dataclass(slots=True)
class RitaConfig:
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_chat_endpoint: str = "/v1/chat/completions"
    llm_model: str = "model"
    llm_timeout_s: int = 20
    llm_temperature: float = 0.2
    llm_max_tokens: int = 64
    stt_model_path: str = str(DEFAULT_MODEL_PATH)
    stt_sample_rate: int = 16000
    audio_max_duration_s: float = 6.0
    audio_silence_s: float = 1.0
    audio_silence_amplitude: float = 0.02
    recordings_dir: str = str(DEFAULT_RECORDINGS_PATH)
    tts_rate: int = 160
    tts_volume: float = 0.95
    debug_timing: bool = False
    backend_base_url: str = DEFAULT_BACKEND_BASE_URL
    backend_events_url: str = f"{DEFAULT_BACKEND_BASE_URL}/events"
    backend_device_code: str = "rita-edge-001"
    backend_device_token: str = ""
    backend_timeout_s: int = 3
    backend_queue_path: str = str(DEFAULT_BACKEND_QUEUE_PATH)
    backend_retry_on_startup: bool = True
    backend_heartbeat_url: str = f"{DEFAULT_BACKEND_BASE_URL}/devices/{{device_code}}/heartbeat"
    backend_heartbeat_on_startup: bool = True
    backend_heartbeat_after_turn: bool = True
    backend_heartbeat_timeout_s: int = 3
    # Sensores GPIO
    pir_gpio_pin: int = 17
    sound_gpio_pin: int = 18


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _build_backend_events_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/events"


def _build_backend_heartbeat_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/devices/{{device_code}}/heartbeat"


def _to_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "si", "sí"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default



def load_config(path: Path = DEFAULT_CONFIG_PATH) -> RitaConfig:
    raw: dict[str, object] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

    defaults = RitaConfig()
    llm_section = _as_dict(raw.get("llm"))
    backend_section = _as_dict(raw.get("backend"))

    llm_base_url = str(llm_section.get("base_url", raw.get("llm_base_url", defaults.llm_base_url)))
    llm_chat_endpoint = str(
        llm_section.get("chat_endpoint", raw.get("llm_chat_endpoint", defaults.llm_chat_endpoint))
    )
    llm_model = str(llm_section.get("model", raw.get("llm_model", defaults.llm_model)))
    llm_timeout_s = int(llm_section.get("timeout_s", raw.get("llm_timeout_s", defaults.llm_timeout_s)))
    llm_temperature = float(
        llm_section.get("temperature", raw.get("llm_temperature", defaults.llm_temperature))
    )
    llm_max_tokens = int(llm_section.get("max_tokens", raw.get("llm_max_tokens", defaults.llm_max_tokens)))

    backend_base_url = str(
        backend_section.get("base_url", raw.get("backend_base_url", defaults.backend_base_url))
    )
    backend_events_url = str(
        backend_section.get(
            "events_url",
            raw.get("backend_events_url", _build_backend_events_url(backend_base_url)),
        )
    )
    backend_heartbeat_url = str(
        backend_section.get(
            "heartbeat_url",
            raw.get("backend_heartbeat_url", _build_backend_heartbeat_url(backend_base_url)),
        )
    )

    config = RitaConfig(
        llm_base_url=llm_base_url,
        llm_chat_endpoint=llm_chat_endpoint,
        llm_model=llm_model,
        llm_timeout_s=llm_timeout_s,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens,
        stt_model_path=str(raw.get("stt_model_path", defaults.stt_model_path)),
        stt_sample_rate=int(raw.get("stt_sample_rate", defaults.stt_sample_rate)),
        audio_max_duration_s=float(raw.get("audio_max_duration_s", defaults.audio_max_duration_s)),
        audio_silence_s=float(raw.get("audio_silence_s", defaults.audio_silence_s)),
        audio_silence_amplitude=float(raw.get("audio_silence_amplitude", defaults.audio_silence_amplitude)),
        recordings_dir=str(raw.get("recordings_dir", defaults.recordings_dir)),
        tts_rate=int(raw.get("tts_rate", defaults.tts_rate)),
        tts_volume=float(raw.get("tts_volume", defaults.tts_volume)),
        debug_timing=_to_bool(raw.get("debug_timing", defaults.debug_timing), defaults.debug_timing),
        backend_base_url=backend_base_url,
        backend_events_url=backend_events_url,
        backend_device_code=str(
            backend_section.get("device_code", raw.get("backend_device_code", defaults.backend_device_code))
        ),
        backend_device_token=str(
            backend_section.get("device_token", raw.get("backend_device_token", defaults.backend_device_token))
        ),
        backend_timeout_s=int(
            backend_section.get("timeout_s", raw.get("backend_timeout_s", defaults.backend_timeout_s))
        ),
        backend_queue_path=str(
            backend_section.get("queue_path", raw.get("backend_queue_path", defaults.backend_queue_path))
        ),
        backend_retry_on_startup=_to_bool(
            backend_section.get(
                "retry_on_startup",
                raw.get("backend_retry_on_startup", defaults.backend_retry_on_startup),
            ),
            defaults.backend_retry_on_startup,
        ),
        backend_heartbeat_url=backend_heartbeat_url,
        backend_heartbeat_on_startup=_to_bool(
            backend_section.get(
                "heartbeat_on_startup",
                raw.get("backend_heartbeat_on_startup", defaults.backend_heartbeat_on_startup),
            ),
            defaults.backend_heartbeat_on_startup,
        ),
        backend_heartbeat_after_turn=_to_bool(
            backend_section.get(
                "heartbeat_after_turn",
                raw.get("backend_heartbeat_after_turn", defaults.backend_heartbeat_after_turn),
            ),
            defaults.backend_heartbeat_after_turn,
        ),
        backend_heartbeat_timeout_s=int(
            backend_section.get(
                "heartbeat_timeout_s",
                raw.get("backend_heartbeat_timeout_s", defaults.backend_heartbeat_timeout_s),
            )
        ),
    )

    config.debug_timing = _to_bool(os.getenv("RITA_DEBUG_TIMING", config.debug_timing), config.debug_timing)
    config.backend_base_url = os.getenv("RITA_BACKEND_BASE_URL", config.backend_base_url)
    config.backend_events_url = os.getenv(
        "RITA_BACKEND_EVENTS_URL",
        _build_backend_events_url(config.backend_base_url),
    )
    config.backend_device_code = os.getenv("RITA_BACKEND_DEVICE_CODE", config.backend_device_code)
    config.backend_device_token = os.getenv("RITA_BACKEND_DEVICE_TOKEN", config.backend_device_token)
    env_backend_timeout = os.getenv("RITA_BACKEND_TIMEOUT_S")
    if env_backend_timeout is not None:
        config.backend_timeout_s = int(env_backend_timeout)
    config.backend_queue_path = os.getenv("RITA_BACKEND_QUEUE_PATH", config.backend_queue_path)
    config.backend_retry_on_startup = _to_bool(
        os.getenv("RITA_BACKEND_RETRY_ON_STARTUP", config.backend_retry_on_startup),
        config.backend_retry_on_startup,
    )
    config.backend_heartbeat_url = os.getenv(
        "RITA_BACKEND_HEARTBEAT_URL",
        _build_backend_heartbeat_url(config.backend_base_url),
    )
    config.backend_heartbeat_on_startup = _to_bool(
        os.getenv("RITA_BACKEND_HEARTBEAT_ON_STARTUP", config.backend_heartbeat_on_startup),
        config.backend_heartbeat_on_startup,
    )
    config.backend_heartbeat_after_turn = _to_bool(
        os.getenv("RITA_BACKEND_HEARTBEAT_AFTER_TURN", config.backend_heartbeat_after_turn),
        config.backend_heartbeat_after_turn,
    )
    env_hb_timeout = os.getenv("RITA_BACKEND_HEARTBEAT_TIMEOUT_S")
    if env_hb_timeout is not None:
        config.backend_heartbeat_timeout_s = int(env_hb_timeout)

    config.llm_base_url = os.getenv("LLM_BASE_URL", config.llm_base_url)
    config.llm_chat_endpoint = os.getenv("LLM_CHAT_ENDPOINT", config.llm_chat_endpoint)
    config.llm_model = os.getenv("LLM_MODEL", config.llm_model)
    env_llm_timeout = os.getenv("LLM_TIMEOUT_S")
    if env_llm_timeout is not None:
        config.llm_timeout_s = int(env_llm_timeout)
    env_llm_temperature = os.getenv("LLM_TEMPERATURE")
    if env_llm_temperature is not None:
        config.llm_temperature = float(env_llm_temperature)
    if env_llm_max_tokens is not None:
        config.llm_max_tokens = int(env_llm_max_tokens)

    # Cargar configuración de sensores desde entorno
    config.pir_gpio_pin = int(os.getenv("RITA_PIR_GPIO_PIN", config.pir_gpio_pin))
    config.sound_gpio_pin = int(os.getenv("RITA_SOUND_GPIO_PIN", config.sound_gpio_pin))

    return config
