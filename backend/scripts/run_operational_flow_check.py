"""
Smoke operativo del backend RITA: flujo completo de eventos de dispositivo.

Objetivo
--------
Simular un flujo controlado y verificar:
- respuestas HTTP
- tiempos de respuesta
- cambios de metricas en /metrics/summary

Uso rapido
----------
Desde backend/:
    python scripts/run_operational_flow_check.py

Con URL y credenciales personalizadas:
    python scripts/run_operational_flow_check.py \
        --base-url http://localhost:8000 \
        --username admin \
        --password admin123

Usar dispositivo existente (si ya tienes token):
    python scripts/run_operational_flow_check.py \
        --device-code edge-001 \
        --device-token <TOKEN>
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from uuid import uuid4

try:
    import requests
except ImportError as exc:  # pragma: no cover - ruta solo informativa
    print("ERROR: Falta el paquete 'requests'.")
    print("Instala con: python -m pip install requests")
    raise SystemExit(1) from exc


def _now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke operativo del flujo de eventos en RITA backend")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL del backend")
    parser.add_argument("--username", default="admin", help="Usuario frontend")
    parser.add_argument("--password", default="admin123", help="Password frontend")
    parser.add_argument(
        "--device-code",
        default=None,
        help="Device code existente. Si no se pasa, se crea un dispositivo de prueba.",
    )
    parser.add_argument(
        "--device-token",
        default=None,
        help="Token plano del dispositivo existente. Requerido si usas --device-code.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout por request en segundos.",
    )
    parser.add_argument(
        "--verbose-body",
        action="store_true",
        help="Muestra cuerpo JSON completo de cada respuesta.",
    )
    return parser.parse_args()


def _timed_request(
    session: requests.Session,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, object] | None = None,
    params: dict[str, object] | None = None,
    timeout: float,
) -> tuple[requests.Response, float]:
    start = time.perf_counter()
    response = session.request(
        method=method,
        url=url,
        headers=headers,
        json=json_body,
        params=params,
        timeout=timeout,
    )
    duration_ms = (time.perf_counter() - start) * 1000.0
    return response, duration_ms


def _safe_json(response: requests.Response) -> dict[str, object] | list[object] | None:
    try:
        return response.json()
    except Exception:
        return None


def _print_result(step: str, response: requests.Response, duration_ms: float, *, verbose_body: bool) -> None:
    print(f"[{step}] {response.request.method} {response.request.path_url}")
    print(f"  status={response.status_code} duration_ms={duration_ms:.1f}")
    if verbose_body:
        payload = _safe_json(response)
        if payload is not None:
            print("  body=")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("  body=<non-json>")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _metric_counters(summary: dict[str, object]) -> dict[str, int]:
    counters = summary.get("counters", {})
    if not isinstance(counters, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in counters.items():
        if isinstance(key, str) and isinstance(value, int):
            out[key] = value
    return out


def _metric_http_rows(summary: dict[str, object]) -> list[dict[str, object]]:
    rows = summary.get("http_requests_total", [])
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _http_count_by_endpoint(rows: list[dict[str, object]], endpoint: str) -> int:
    total = 0
    for row in rows:
        if row.get("endpoint") == endpoint and isinstance(row.get("count"), int):
            total += int(row["count"])
    return total


def _find_device_id(devices_json: object, device_code: str) -> int | None:
    if not isinstance(devices_json, list):
        return None
    for item in devices_json:
        if isinstance(item, dict) and item.get("device_code") == device_code and isinstance(item.get("id"), int):
            return int(item["id"])
    return None


def main() -> int:
    args = _parse_args()
    base_url = args.base_url.rstrip("/")
    session = requests.Session()

    print("=== RITA Backend Operational Flow Check ===")
    print(f"base_url={base_url}")

    # 1) Login frontend
    login_body = {"username": args.username, "password": args.password}
    resp_login, ms_login = _timed_request(
        session,
        "POST",
        f"{base_url}/auth/login",
        json_body=login_body,
        timeout=args.timeout,
    )
    _print_result("login", resp_login, ms_login, verbose_body=args.verbose_body)
    if resp_login.status_code != 200:
        print("Fallo en login; abortando.")
        return 1

    login_json = _safe_json(resp_login)
    if not isinstance(login_json, dict) or not isinstance(login_json.get("access_token"), str):
        print("Respuesta de login invalida; abortando.")
        return 1

    frontend_token = str(login_json["access_token"])
    frontend_headers = _auth_headers(frontend_token)

    # Baseline metrics
    resp_metrics_before, ms_metrics_before = _timed_request(
        session,
        "GET",
        f"{base_url}/metrics/summary",
        headers=frontend_headers,
        timeout=args.timeout,
    )
    _print_result("metrics_before", resp_metrics_before, ms_metrics_before, verbose_body=False)
    if resp_metrics_before.status_code != 200:
        print("No se pudieron obtener metricas iniciales; abortando.")
        return 1

    metrics_before = _safe_json(resp_metrics_before)
    if not isinstance(metrics_before, dict):
        print("Formato de metricas iniciales invalido; abortando.")
        return 1

    counters_before = _metric_counters(metrics_before)
    http_before = _metric_http_rows(metrics_before)

    # 2) Crear o usar dispositivo
    created_user_id: int | None = None
    device_code: str
    device_token: str
    device_id: int | None = None

    if args.device_code:
        if not args.device_token:
            print("Si usas --device-code debes pasar --device-token.")
            return 1
        device_code = args.device_code
        device_token = args.device_token

        resp_devices, ms_devices = _timed_request(
            session,
            "GET",
            f"{base_url}/devices",
            headers=frontend_headers,
            timeout=args.timeout,
        )
        _print_result("list_devices", resp_devices, ms_devices, verbose_body=False)
        devices_json = _safe_json(resp_devices)
        device_id = _find_device_id(devices_json, device_code)
    else:
        run_id = _now_tag()

        create_user_body = {
            "full_name": f"Smoke Ops User {run_id}",
            "birth_date": None,
            "notes": "Created by run_operational_flow_check.py",
        }
        resp_user, ms_user = _timed_request(
            session,
            "POST",
            f"{base_url}/users",
            headers=frontend_headers,
            json_body=create_user_body,
            timeout=args.timeout,
        )
        _print_result("create_user", resp_user, ms_user, verbose_body=args.verbose_body)
        if resp_user.status_code != 201:
            print("No se pudo crear usuario de prueba; abortando.")
            return 1

        user_json = _safe_json(resp_user)
        if not isinstance(user_json, dict) or not isinstance(user_json.get("id"), int):
            print("Respuesta de usuario invalida; abortando.")
            return 1
        created_user_id = int(user_json["id"])

        device_code = f"smoke-device-{run_id}"
        create_device_body = {
            "user_id": created_user_id,
            "device_code": device_code,
            "device_name": f"Smoke Device {run_id}",
            "location_name": "Lab",
            "is_active": True,
        }
        resp_device, ms_device = _timed_request(
            session,
            "POST",
            f"{base_url}/devices",
            headers=frontend_headers,
            json_body=create_device_body,
            timeout=args.timeout,
        )
        _print_result("create_device", resp_device, ms_device, verbose_body=args.verbose_body)
        if resp_device.status_code != 201:
            print("No se pudo crear dispositivo de prueba; abortando.")
            return 1

        device_json = _safe_json(resp_device)
        if not isinstance(device_json, dict):
            print("Respuesta de dispositivo invalida; abortando.")
            return 1
        if not isinstance(device_json.get("device_token"), str):
            print("No se recibio device_token en provision; abortando.")
            return 1

        device_token = str(device_json["device_token"])
        if isinstance(device_json.get("id"), int):
            device_id = int(device_json["id"])

    print(f"Dispositivo en uso: device_code={device_code} device_id={device_id}")

    # 3) Secuencia controlada de eventos
    device_headers = {"X-Device-Token": device_token}

    trace_info = str(uuid4())
    payload_info = {
        "schema_version": "1.0",
        "trace_id": trace_info,
        "device_code": device_code,
        "event_type": "conversation_anomaly",
        "severity": "low",
        "source": "ops-smoke",
        "user_text": "test informativo",
    }
    resp_info, ms_info = _timed_request(
        session,
        "POST",
        f"{base_url}/events",
        headers=device_headers,
        json_body=payload_info,
        timeout=args.timeout,
    )
    _print_result("event_info", resp_info, ms_info, verbose_body=args.verbose_body)

    trace_incident = str(uuid4())
    payload_incident = {
        "schema_version": "1.0",
        "trace_id": trace_incident,
        "device_code": device_code,
        "event_type": "help_request",
        "severity": "high",
        "source": "ops-smoke",
        "user_text": "necesito ayuda",
        "payload_json": {"reason": "smoke_test"},
    }
    resp_incident, ms_incident = _timed_request(
        session,
        "POST",
        f"{base_url}/events",
        headers=device_headers,
        json_body=payload_incident,
        timeout=args.timeout,
    )
    _print_result("event_incident", resp_incident, ms_incident, verbose_body=args.verbose_body)

    resp_replay, ms_replay = _timed_request(
        session,
        "POST",
        f"{base_url}/events",
        headers=device_headers,
        json_body=payload_incident,
        timeout=args.timeout,
    )
    _print_result("event_replay", resp_replay, ms_replay, verbose_body=args.verbose_body)

    trace_alert = str(uuid4())
    payload_alert = {
        "schema_version": "1.0",
        "trace_id": trace_alert,
        "device_code": device_code,
        "event_type": "emergency_keyword_detected",
        "severity": "critical",
        "source": "ops-smoke",
        "user_text": "ayuda urgente",
        "payload_json": {"keyword": "socorro"},
    }
    resp_alert, ms_alert = _timed_request(
        session,
        "POST",
        f"{base_url}/events",
        headers=device_headers,
        json_body=payload_alert,
        timeout=args.timeout,
    )
    _print_result("event_alert", resp_alert, ms_alert, verbose_body=args.verbose_body)

    trace_invalid = str(uuid4())
    payload_invalid = {
        "schema_version": "1.0",
        "trace_id": trace_invalid,
        "device_code": device_code,
        "event_type": "fall_suspected",
        "source": "ops-smoke",
    }
    resp_invalid, ms_invalid = _timed_request(
        session,
        "POST",
        f"{base_url}/events",
        headers=device_headers,
        json_body=payload_invalid,
        timeout=args.timeout,
    )
    _print_result("event_invalid_semantic", resp_invalid, ms_invalid, verbose_body=args.verbose_body)

    # 4) Consultas de lectura
    query_params_events: dict[str, object] = {"order": "desc", "limit": 20, "offset": 0}
    if created_user_id is not None:
        query_params_events["user_id"] = created_user_id
    if device_id is not None:
        query_params_events["device_id"] = device_id

    resp_events, ms_events = _timed_request(
        session,
        "GET",
        f"{base_url}/events",
        headers=frontend_headers,
        params=query_params_events,
        timeout=args.timeout,
    )
    _print_result("get_events", resp_events, ms_events, verbose_body=args.verbose_body)

    query_params_incidents: dict[str, object] = {"order": "desc", "limit": 20, "offset": 0}
    if created_user_id is not None:
        query_params_incidents["user_id"] = created_user_id
    if device_id is not None:
        query_params_incidents["device_id"] = device_id

    resp_incidents, ms_incidents = _timed_request(
        session,
        "GET",
        f"{base_url}/incidents",
        headers=frontend_headers,
        params=query_params_incidents,
        timeout=args.timeout,
    )
    _print_result("get_incidents", resp_incidents, ms_incidents, verbose_body=args.verbose_body)

    query_params_alerts: dict[str, object] = {"order": "desc", "limit": 20, "offset": 0}
    if created_user_id is not None:
        query_params_alerts["user_id"] = created_user_id

    resp_alerts, ms_alerts = _timed_request(
        session,
        "GET",
        f"{base_url}/alerts",
        headers=frontend_headers,
        params=query_params_alerts,
        timeout=args.timeout,
    )
    _print_result("get_alerts", resp_alerts, ms_alerts, verbose_body=args.verbose_body)

    resp_metrics_after, ms_metrics_after = _timed_request(
        session,
        "GET",
        f"{base_url}/metrics/summary",
        headers=frontend_headers,
        timeout=args.timeout,
    )
    _print_result("metrics_after", resp_metrics_after, ms_metrics_after, verbose_body=False)
    if resp_metrics_after.status_code != 200:
        print("No se pudieron obtener metricas finales.")
        return 1

    metrics_after = _safe_json(resp_metrics_after)
    if not isinstance(metrics_after, dict):
        print("Formato de metricas finales invalido.")
        return 1

    # 5) Mostrar cambios de metricas
    counters_after = _metric_counters(metrics_after)
    tracked = [
        "events_received_total",
        "events_rejected_semantic_total",
        "events_idempotent_replay_total",
        "incidents_created_total",
        "alerts_created_total",
        "device_auth_failed_total",
        "device_forbidden_total",
        "audit_required_failure_total",
    ]

    print("\n=== Delta de metricas (counters) ===")
    for key in tracked:
        before = counters_before.get(key, 0)
        after = counters_after.get(key, 0)
        print(f"{key}: before={before} after={after} delta={after - before}")

    http_after = _metric_http_rows(metrics_after)
    endpoints_to_show = [
        "/events",
        "/incidents",
        "/alerts",
        "/metrics/summary",
    ]
    print("\n=== Delta HTTP requests por endpoint ===")
    for endpoint in endpoints_to_show:
        before = _http_count_by_endpoint(http_before, endpoint)
        after = _http_count_by_endpoint(http_after, endpoint)
        print(f"{endpoint}: before={before} after={after} delta={after - before}")

    print("\n=== Expectativas rapidas ===")
    print(f"event_info status esperado 201 -> {resp_info.status_code}")
    print(f"event_incident status esperado 201 -> {resp_incident.status_code}")
    print(f"event_replay status esperado 200 -> {resp_replay.status_code}")
    print(f"event_alert status esperado 201 -> {resp_alert.status_code}")
    print(f"event_invalid_semantic status esperado 422 -> {resp_invalid.status_code}")

    print("\nScript completado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
