from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import time
from typing import Optional
from uuid import uuid4

import requests

from src.audio.recorder import MicrophoneUnavailableError
from src.config import RitaConfig
from src.conversation.intent_router import (
    detect_backend_event_type,
    followup_response,
    infer_local_topic,
    local_response,
)
from src.conversation.llm_client import (
    LlamaCppClient,
    LlmProvider,
    LlmProviderError,
    LlmResponse,
    sanitize_llm_response,
)
from src.conversation.prompts import build_prompt
from src.conversation.session import ConversationSession, IntentType
from src.integrations.event_queue import LocalEventQueue
from src.integrations.seniorcare_adapters import RitaVoiceStack, build_rita_voice_stack
from src.safety.keyword_detector import KeywordDetector
from src.stt.vosk_transcriber import SttError
from src.tts.engine import TtsError

EXIT_COMMANDS = ("salir", "adios", "adiós", "terminar")
_EVENT_SEVERITY = {
    "distress": "medium",
    "fall": "high",
    "emergency": "high",
    "checkin": "low",
    "user_speech": "low",
    "assistant_response": "low",
}

_INCIDENT_RESOLVED_RE = re.compile(
    r"\bestoy\s+bien\b"
    r"|\bno\s+me\s+duele\s+nada\b"
    r"|\bno\s+hay\s+sangre\b"
    r"|\bnada\s+de\s+eso\b"
    r"|\bsolo\s+quiero\s+hablar\b",
    re.IGNORECASE,
)
_HUMOR_REQUEST_RE = re.compile(
    r"\bchiste\b|\bbroma\b|\balgo\s+gracioso\b|\bhazme\s+re[ií]r\b",
    re.IGNORECASE,
)

HUMAN_FALLBACK_RESPONSE = (
    "Ahora mismo me cuesta un poco concentrarme, pero sigo aquí contigo. "
    "¿Me lo puedes repetir de otra forma, por favor?"
)


def send_event_to_backend(
    event_type: str,
    severity: str,
    user_text: str,
    rita_text: str,
    payload_json: dict[str, object] | None,
    *,
    backend_url: str = "http://localhost:8000/events",
    device_code: str = "rita-edge-001",
    device_token: str | None = None,
    timeout_s: int = 3,
) -> bool:
    """Send one event to RITA backend. Never raises to caller."""
    body = build_backend_event(
        event_type=event_type,
        severity=severity,
        user_text=user_text,
        rita_text=rita_text,
        payload_json=payload_json,
        device_code=device_code,
    )
    return send_backend_event_payload(
        body,
        backend_url=backend_url,
        device_token=device_token,
        timeout_s=timeout_s,
    )


def build_backend_event(
    event_type: str,
    severity: str,
    user_text: str,
    rita_text: str,
    payload_json: dict[str, object] | None,
    device_code: str,
    schema_version: str = "1.0",
    trace_id: str | None = None,
) -> dict[str, object]:
    resolved_trace_id = trace_id or str(uuid4())
    return {
        "schema_version": schema_version,
        "trace_id": resolved_trace_id,
        "device_code": device_code,
        "event_type": event_type,
        "severity": severity,
        "source": "rita-edge",
        "user_text": user_text,
        "rita_text": rita_text,
        "payload_json": payload_json or {},
    }


def send_backend_event_payload(
    event: dict[str, object],
    *,
    backend_url: str,
    device_token: str | None = None,
    timeout_s: int,
) -> bool:
    # Backward compatibility for events already queued with older payload schema.
    event.setdefault("schema_version", "1.0")
    event.setdefault("trace_id", str(uuid4()))
    headers = {"X-Device-Token": device_token.strip()} if device_token and device_token.strip() else None
    try:
        response = requests.post(backend_url, json=event, headers=headers, timeout=timeout_s)
        if response.status_code >= 400:
            print(f"[WARN] Backend devolvió {response.status_code} en POST /events")
            return False
    except requests.RequestException as exc:
        print(f"[WARN] No se pudo enviar evento al backend: {exc}")
        return False
    return True


def send_heartbeat_to_backend(
    *,
    heartbeat_url: str,
    device_code: str,
    device_token: str | None = None,
    timeout_s: int = 3,
) -> bool:
    """Send one heartbeat to RITA backend. Never raises to caller."""
    if "{device_code}" in heartbeat_url:
        url = heartbeat_url.format(device_code=device_code)
    else:
        base = heartbeat_url.rstrip("/")
        if base.endswith("/heartbeat"):
            url = base
        elif base.endswith("/devices"):
            url = f"{base}/{device_code}/heartbeat"
        else:
            url = f"{base}/devices/{device_code}/heartbeat"

    headers = {"X-Device-Token": device_token.strip()} if device_token and device_token.strip() else None
    try:
        response = requests.post(url, headers=headers, timeout=timeout_s)
        if response.status_code >= 400:
            print(f"[WARN] Backend devolvió {response.status_code} en POST heartbeat")
            return False
    except requests.RequestException as exc:
        print(f"[WARN] No se pudo enviar heartbeat al backend: {exc}")
        return False
    return True


@dataclass(slots=True)
class TurnResult:
    user_text: str
    rita_text: str
    should_exit: bool


class VoiceAssistant:
    def __init__(self, config: RitaConfig, text_mode: bool = False) -> None:
        self.config = config
        self.text_mode = text_mode
        self.session = ConversationSession(max_turns=8)
        self.risk_detector = KeywordDetector()
        self.llm: LlmProvider = LlamaCppClient(
            base_url=config.llm_base_url,
            chat_endpoint=config.llm_chat_endpoint,
            model=config.llm_model,
            timeout_s=config.llm_timeout_s,
            temperature=config.llm_temperature,
            max_tokens=config.llm_max_tokens,
        )
        self.voice_stack: Optional[RitaVoiceStack] = None
        self._last_record_s: float = 0.0
        self._last_stt_s: float = 0.0
        self._last_stt_confidence: float | None = None
        self._event_queue = LocalEventQueue(Path(config.backend_queue_path))

        if not text_mode:
            recordings_dir = Path(config.recordings_dir)
            self.voice_stack = build_rita_voice_stack(
                recordings_dir=recordings_dir,
                model_path=Path(config.stt_model_path),
                sample_rate=config.stt_sample_rate,
                silence_amplitude=config.audio_silence_amplitude,
                tts_rate=config.tts_rate,
                tts_volume=config.tts_volume,
            )
            self.risk_detector = self.voice_stack.risk_detector

        if self.config.backend_retry_on_startup:
            self._retry_queued_events()
        if self.config.backend_heartbeat_on_startup:
            self._send_heartbeat_opportunistic()

    def _update_local_ui(self, status: str, user_text: str = "", rita_text: str = "", emotion: str = "") -> None:
        if self.text_mode: return
        payload = {"status": status, "user_text": user_text, "rita_text": rita_text}
        if emotion: payload["emotion"] = emotion
        try: requests.post("http://localhost:5000/api/update", json=payload, timeout=0.1)
        except Exception: pass

    def _safe_speak(self, text: str, emotion: str = "") -> float:
        self._update_local_ui(status="hablando", rita_text=text, emotion=emotion)
        if self.text_mode:
            print("[VOICE] Modo texto: TTS deshabilitado.")
            self._update_local_ui(status="esperando", rita_text=text)
            return 0.0
        if self.voice_stack is None:
            print("[VOICE] ⚠ voice_stack es None: no se puede reproducir audio.")
            self._update_local_ui(status="esperando", rita_text=text)
            return 0.0
        t0 = time.perf_counter()
        print(f"[VOICE] Iniciando TTS para: {text[:50]}..." if len(text) > 50 else f"[VOICE] Iniciando TTS para: {text}")
        try:
            self.voice_stack.tts.speak(text)
            elapsed = time.perf_counter() - t0
            print(f"[VOICE] ✓ TTS completado en {elapsed:.2f}s")
            self._update_local_ui(status="esperando", rita_text=text)
            return elapsed
        except TtsError as exc:
            print(f"[VOICE] ✗ TtsError capturado: {exc}")
            self._update_local_ui(status="esperando", rita_text=text)
            return time.perf_counter() - t0
        except Exception as exc:
            print(f"[VOICE] ✗ Excepción inesperada en TTS: {type(exc).__name__}: {exc}")
            self._update_local_ui(status="esperando", rita_text=text)
            return time.perf_counter() - t0

    def _normalize_reply_punctuation(self, text: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return cleaned
        if cleaned[-1] in ".!?":
            return cleaned
        words = cleaned.split()
        # Si la última palabra parece truncada (< 5 chars) y hay texto suficiente antes,
        # recortarla para evitar finales raros como "…agua fres"
        if len(words) >= 2 and len(words[-1]) < 5:
            candidate = " ".join(words[:-1]).rstrip(" ,;:")
            if len(candidate) >= 8:
                return f"{candidate}."
        # Cerrar la frase con punto cuando no haya puntuación final
        if len(cleaned) >= 8:
            return f"{cleaned}."
        return cleaned

    def _should_close_fall_incident_now(self, user_text: str) -> bool:
        text = user_text.strip().lower()
        return bool(_INCIDENT_RESOLVED_RE.search(text) or _HUMOR_REQUEST_RE.search(text))

    def _fall_to_normal_transition(self, user_text: str) -> str:
        transition = (
            "Me alegra que estés bien. Si notas dolor, mareo o sangre, dímelo enseguida. "
            "Seguimos con una conversación tranquila."
        )
        if _HUMOR_REQUEST_RE.search(user_text):
            return (
                "Me alegra que estés bien. Si notas dolor, mareo o sangre, dímelo enseguida. "
                "Ahora sí, te cuento un chiste: ¿Qué hace una abeja en el gimnasio? ¡Zum-ba!"
            )
        return transition

    def _send_backend_event_if_needed(self, event_type: str | None, user_text: str, rita_text: str) -> None:
        if event_type is None:
            return
        payload_json: dict[str, object] = {
            "origin": "voice",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self._last_stt_confidence is not None:
            payload_json["confidence"] = round(self._last_stt_confidence, 4)

        event = build_backend_event(
            event_type=event_type,
            severity=_EVENT_SEVERITY.get(event_type, "low"),
            user_text=user_text,
            rita_text=rita_text,
            payload_json=payload_json,
            device_code=self.config.backend_device_code,
        )
        sent = send_backend_event_payload(
            event,
            backend_url=self.config.backend_events_url,
            device_token=self.config.backend_device_token,
            timeout_s=self.config.backend_timeout_s,
        )
        if sent:
            self._retry_queued_events()
            return

        self._event_queue.enqueue(event)

    def _send_conversation_event(
        self,
        *,
        event_type: str,
        user_text: str | None,
        rita_text: str | None,
        llm_metadata: dict[str, object] | None = None,
    ) -> None:
        payload_json: dict[str, object] = {
            "origin": "voice" if not self.text_mode else "text",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if llm_metadata:
            payload_json.update(llm_metadata)
        if self._last_stt_confidence is not None:
            payload_json["confidence"] = round(self._last_stt_confidence, 4)

        event = build_backend_event(
            event_type=event_type,
            severity=_EVENT_SEVERITY[event_type],
            user_text=(user_text or "").strip(),
            rita_text=(rita_text or "").strip(),
            payload_json=payload_json,
            device_code=self.config.backend_device_code,
        )
        print(
            f"[EVENT] Enviando {event_type} trace_id={event['trace_id']} device={self.config.backend_device_code}"
        )
        sent = send_backend_event_payload(
            event,
            backend_url=self.config.backend_events_url,
            device_token=self.config.backend_device_token,
            timeout_s=self.config.backend_timeout_s,
        )
        if sent:
            print(f"[EVENT] {event_type} persistido en backend")
            return

        print(f"[EVENT] {event_type} encolado para reintento")
        self._event_queue.enqueue(event)

    def _retry_queued_events(self) -> None:
        sent, remaining = self._event_queue.retry_pending(
            lambda e: send_backend_event_payload(
                e,
                backend_url=self.config.backend_events_url,
                device_token=self.config.backend_device_token,
                timeout_s=self.config.backend_timeout_s,
            )
        )
        if sent or remaining:
            print(f"[INFO] Cola backend reenviada: enviados={sent}, pendientes={remaining}")

    def _send_heartbeat_opportunistic(self) -> None:
        sent = send_heartbeat_to_backend(
            heartbeat_url=self.config.backend_heartbeat_url,
            device_code=self.config.backend_device_code,
            device_token=self.config.backend_device_token,
            timeout_s=self.config.backend_heartbeat_timeout_s,
        )
        if not sent:
            # Encolar el heartbeat fallido como evento para reenviarlo cuando
            # se restaure la conexión. El backend lo registrará como latido
            # con marca de tiempo correcta al recibirlo.
            hb_event = build_backend_event(
                event_type="heartbeat",
                severity="low",
                user_text="",
                rita_text="",
                payload_json={
                    "origin": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "queued_offline": True,
                },
                device_code=self.config.backend_device_code,
            )
            self._event_queue.enqueue(hb_event)
            print("[HEARTBEAT] Sin conexión — latido encolado para reintento")

    def _after_turn_heartbeat(self) -> None:
        if self.config.backend_heartbeat_after_turn:
            self._send_heartbeat_opportunistic()

    def _print_timing(
        self,
        record_s: float,
        stt_s: float,
        prompt_s: float,
        llm_s: float,
        tts_s: float,
        total_s: float,
        tokens: tuple[int, int] = (0, 0),
    ) -> None:
        if not self.config.debug_timing:
            return
        
        p_tok, c_tok = tokens
        tps = c_tok / llm_s if llm_s > 0 else 0
        
        print(
            "[TIMING] "
            f"record={record_s:.3f}s | "
            f"stt={stt_s:.3f}s | "
            f"prompt={prompt_s:.3f}s | "
            f"llm={llm_s:.3f}s (tokens: p{p_tok}/c{c_tok}, {tps:.1f} t/s) | "
            f"tts={tts_s:.3f}s | "
            f"total={total_s:.3f}s"
        )

    def greet(self) -> str:
        text = "Hola, soy RITA. Estoy aqui para conversar contigo."
        self._safe_speak(text)
        return text

    def listen_user(self) -> str:
        self._update_local_ui(status="escuchando")
        if self.text_mode:
            self._last_record_s = 0.0
            self._last_stt_s = 0.0
            self._last_stt_confidence = None
            return input("Tu: ").strip()

        if self.voice_stack is None:
            raise RuntimeError("El modo voz requiere inicializar grabador y STT.")

        try:
            record_start = time.perf_counter()
            wav_path = self.voice_stack.recorder.record(
                max_duration_s=self.config.audio_max_duration_s,
                silence_s=self.config.audio_silence_s,
            )
            self._last_record_s = time.perf_counter() - record_start
        except MicrophoneUnavailableError as exc:
            print(f"[ERROR] Microfono no disponible: {exc}")
            self._last_record_s = 0.0
            self._last_stt_s = 0.0
            self._last_stt_confidence = None
            return ""

        try:
            stt_start = time.perf_counter()
            transcript = self.voice_stack.stt.transcribe_file(wav_path)
            self._last_stt_s = time.perf_counter() - stt_start
            confidence = getattr(transcript, "confidence", None)
            self._last_stt_confidence = float(confidence) if isinstance(confidence, (int, float)) else None
            return transcript.text.strip()
        except SttError as exc:
            print(f"[WARN] Fallo de transcripcion: {exc}")
            self._last_stt_s = 0.0
            self._last_stt_confidence = None
            return ""

    def run_turn(self, user_text: str) -> TurnResult:
        self._update_local_ui(status="pensando", user_text=user_text)
        turn_start = time.perf_counter()
        record_s = self._last_record_s
        stt_s = self._last_stt_s
        prompt_s = 0.0
        llm_s = 0.0
        tts_s = 0.0

        lowered = user_text.lower().strip()
        if lowered:
            self._send_conversation_event(
                event_type="user_speech",
                user_text=user_text,
                rita_text=None,
            )
        if lowered in EXIT_COMMANDS:
            self.session.last_intent = "exit"
            farewell = "Hasta luego. Cuando quieras, volvemos a hablar."
            self._send_conversation_event(
                event_type="assistant_response",
                user_text=None,
                rita_text=farewell,
            )
            tts_s = self._safe_speak(farewell)
            self._after_turn_heartbeat()
            self._print_timing(record_s, stt_s, prompt_s, llm_s, tts_s, time.perf_counter() - turn_start)
            return TurnResult(user_text=user_text, rita_text=farewell, should_exit=True)

        risk = self.risk_detector.detect(user_text)
        intent: IntentType = self.session.update_state(user_text=user_text, risk_detected=bool(risk))
        backend_event_type = detect_backend_event_type(user_text, intent)

        # --- Fall protocol takes full priority once opened ---
        if self.session.fall_incident_is_active():
            if self._should_close_fall_incident_now(user_text):
                self.session.close_incident()
                self.session.conversation_mode = "normal"
                transition_text = self._fall_to_normal_transition(user_text)
                self.session.add_user(user_text)
                self.session.add_assistant(transition_text)
                self._send_conversation_event(
                    event_type="assistant_response",
                    user_text=None,
                    rita_text=transition_text,
                )
                self._send_backend_event_if_needed(backend_event_type, user_text, transition_text)
                tts_s = self._safe_speak(transition_text)
                self._after_turn_heartbeat()
                self._print_timing(record_s, stt_s, prompt_s, llm_s, tts_s, time.perf_counter() - turn_start)
                return TurnResult(user_text=user_text, rita_text=transition_text, should_exit=False)

            protocol_text = self.session.fall_protocol_next(user_text)
            self.session.add_user(user_text)
            self.session.add_assistant(protocol_text)
            self._send_conversation_event(
                event_type="assistant_response",
                user_text=None,
                rita_text=protocol_text,
            )
            self._send_backend_event_if_needed(backend_event_type, user_text, protocol_text)
            tts_s = self._safe_speak(protocol_text)
            self._after_turn_heartbeat()
            self._print_timing(record_s, stt_s, prompt_s, llm_s, tts_s, time.perf_counter() - turn_start)
            return TurnResult(user_text=user_text, rita_text=protocol_text, should_exit=False)

        # --- Trigger that opens the fall protocol ---
        if self.session.is_fall_trigger(user_text):
            self.session.open_fall_incident()
            protocol_text = self.session.fall_protocol_next(user_text)
            self.session.add_user(user_text)
            self.session.add_assistant(protocol_text)
            self._send_conversation_event(
                event_type="assistant_response",
                user_text=None,
                rita_text=protocol_text,
            )
            self._send_backend_event_if_needed("fall", user_text, protocol_text)
            tts_s = self._safe_speak(protocol_text)
            self._after_turn_heartbeat()
            self._print_timing(record_s, stt_s, prompt_s, llm_s, tts_s, time.perf_counter() - turn_start)
            return TurnResult(user_text=user_text, rita_text=protocol_text, should_exit=False)

        # --- Other risk keywords (ayuda, socorro...) keep generic response ---
        if risk or intent == "emergency":
            risk_text = self.risk_detector.emergency_response()
            self.session.add_user(user_text)
            self.session.add_assistant(risk_text)
            event_type = backend_event_type or "emergency"
            self._send_conversation_event(
                event_type="assistant_response",
                user_text=None,
                rita_text=risk_text,
            )
            self._send_backend_event_if_needed(event_type, user_text, risk_text)
            tts_s = self._safe_speak(risk_text)
            self._after_turn_heartbeat()
            self._print_timing(record_s, stt_s, prompt_s, llm_s, tts_s, time.perf_counter() - turn_start)
            return TurnResult(user_text=user_text, rita_text=risk_text, should_exit=False)

        followup_reply = followup_response(user_text, self.session.last_local_topic)
        if followup_reply:
            self.session.last_local_topic = None
            self.session.add_user(user_text)
            self.session.add_assistant(followup_reply)
            self._send_conversation_event(
                event_type="assistant_response",
                user_text=None,
                rita_text=followup_reply,
            )
            self._send_backend_event_if_needed(backend_event_type, user_text, followup_reply)
            tts_s = self._safe_speak(followup_reply)
            self._after_turn_heartbeat()
            self._print_timing(record_s, stt_s, prompt_s, llm_s, tts_s, time.perf_counter() - turn_start)
            return TurnResult(user_text=user_text, rita_text=followup_reply, should_exit=False)

        local_reply = local_response(user_text, intent)
        if local_reply:
            self.session.last_local_topic = infer_local_topic(user_text)
            self.session.add_user(user_text)
            self.session.add_assistant(local_reply)
            self._send_conversation_event(
                event_type="assistant_response",
                user_text=None,
                rita_text=local_reply,
            )
            self._send_backend_event_if_needed(backend_event_type, user_text, local_reply)
            tts_s = self._safe_speak(local_reply)
            self._after_turn_heartbeat()
            self._print_timing(record_s, stt_s, prompt_s, llm_s, tts_s, time.perf_counter() - turn_start)
            return TurnResult(user_text=user_text, rita_text=local_reply, should_exit=False)

        self.session.last_local_topic = None
        prompt_start = time.perf_counter()
        prompt = build_prompt(
            user_text=user_text,
            history=self.session.history_text(last_turns=3, max_chars=300),
            conversation_mode=self.session.conversation_mode,
            intent=intent,
            user_name=self.session.user_name,
            incident_info={
                "incident_type": self.session.incident_type,
                "incident_location": self.session.incident_location,
                "can_call": self.session.can_call,
            } if self.session.incident_type else None,
        )
        prompt_s = time.perf_counter() - prompt_start

        llm_start = time.perf_counter()
        try:
            print(f"[LLM] Llamando a backend real en {self.config.llm_base_url}...")
            # LlamaCppClient has its own timeout in requests.post
            reply = self.llm.generate(prompt)
        except LlmProviderError as exc:
            llm_s = time.perf_counter() - llm_start
            print(f"[LLM] Error o Timeout (fallo tras {llm_s:.2f}s): {exc}")
            reply = HUMAN_FALLBACK_RESPONSE
        except Exception as exc:
            llm_s = time.perf_counter() - llm_start
            print(f"[LLM] Error inesperado (fallo tras {llm_s:.2f}s): {type(exc).__name__}")
            reply = HUMAN_FALLBACK_RESPONSE
        else:
            llm_s = time.perf_counter() - llm_start
            print(f"[LLM] Respuesta recibida en {llm_s:.2f}s")
            reply = sanitize_llm_response(llm_resp.content, user_name=self.session.user_name)
            if not reply:
                reply = "Ahora mismo no tengo una respuesta clara. ¿Puedes repetirlo?"
            else:
                reply = self._normalize_reply_punctuation(reply)
            
            emotion_tag = ""
            import re
            match = re.search(r"\[EMO:\s*([A-Za-z]+)\]", reply, re.IGNORECASE)
            if match:
                emotion_tag = match.group(1).lower()
                reply = re.sub(r"\[EMO:\s*[A-Za-z]+\]", "", reply, flags=re.IGNORECASE).strip()
            
            # Metadata for monitoring
            llm_metadata = {
                "llm_latency_s": round(llm_s, 2),
                "prompt_tokens": llm_resp.prompt_tokens,
                "completion_tokens": llm_resp.completion_tokens,
                "tokens_per_second": round(llm_resp.completion_tokens / llm_s, 2) if llm_s > 0 else 0
            }

        if intent == "personal_info" and self.session.user_name:
            if self.session.user_name.lower() not in reply.lower():
                reply = f"Encantada, {self.session.user_name}. {reply}"

        self.session.add_user(user_text)
        self.session.add_assistant(reply)
        self._send_conversation_event(
            event_type="assistant_response",
            user_text=None,
            rita_text=reply,
            llm_metadata=llm_metadata if 'llm_metadata' in locals() else None
        )
        self._send_backend_event_if_needed(backend_event_type, user_text, reply)
        tts_s = self._safe_speak(reply, emotion=emotion_tag if 'emotion_tag' in locals() else "")
        self._after_turn_heartbeat()
        
        tokens = (llm_resp.prompt_tokens, llm_resp.completion_tokens) if 'llm_resp' in locals() else (0, 0)
        self._print_timing(record_s, stt_s, prompt_s, llm_s, tts_s, time.perf_counter() - turn_start, tokens)
        return TurnResult(user_text=user_text, rita_text=reply, should_exit=False)
