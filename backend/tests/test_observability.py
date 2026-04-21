"""Tests for paso 6: request_id middleware, request logging, and consistent error format."""
from __future__ import annotations

import logging
import uuid
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, register_models
from app.db.session import get_db
from app.main import app


# ---------------------------------------------------------------------------
# Shared test fixture — same engine pattern as test_security_api.py
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    register_models()
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _login(client: TestClient) -> str:
    response = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {_login(client)}"}


# ---------------------------------------------------------------------------
# 1.  X-Request-ID middleware
# ---------------------------------------------------------------------------


def test_response_always_contains_request_id(client: TestClient) -> None:
    """Every response must have X-Request-ID regardless of auth status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    rid = response.headers["x-request-id"]
    assert rid  # must not be empty


def test_generated_request_id_is_valid_uuid(client: TestClient) -> None:
    """When the client does not send X-Request-ID, the server generates a valid UUID4."""
    response = client.get("/health")
    rid = response.headers["x-request-id"]
    parsed = uuid.UUID(rid)  # raises ValueError if not valid UUID
    assert str(parsed) == rid


def test_client_supplied_request_id_is_echoed(client: TestClient) -> None:
    """When the client supplies X-Request-ID, the same value must be returned."""
    custom_id = "my-trace-abc-123"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers["x-request-id"] == custom_id


def test_request_id_present_on_error_response(client: TestClient) -> None:
    """404 responses must also carry X-Request-ID."""
    response = client.get("/no-such-endpoint-xyz", headers=_auth_headers(client))
    assert "x-request-id" in response.headers


# ---------------------------------------------------------------------------
# 2.  Consistent error format — HTTPException cases
# ---------------------------------------------------------------------------


def _assert_error_envelope(body: dict, expected_code: int, expected_error: str) -> None:
    assert body["code"] == expected_code
    assert body["error"] == expected_error
    assert isinstance(body["message"], str)
    assert len(body["message"]) > 0
    assert "request_id" in body  # field present (may be None if middleware not reached)


def test_404_returns_consistent_error_format(client: TestClient) -> None:
    response = client.get("/no-such-endpoint-xyz", headers=_auth_headers(client))
    assert response.status_code == 404
    _assert_error_envelope(response.json(), 404, "not_found")


def test_401_returns_consistent_error_format(client: TestClient) -> None:
    """Accessing a protected endpoint without auth returns 401 in error envelope."""
    response = client.get("/events")
    assert response.status_code == 401
    body = response.json()
    _assert_error_envelope(body, 401, "unauthorized")
    # WWW-Authenticate header must still be present (RFC 7235).
    assert "www-authenticate" in response.headers


def test_401_returns_consistent_error_format_for_invalid_device_token(client: TestClient) -> None:
    """Sending a wrong device token must return 401 in error envelope."""
    # We need a valid device_code on the system; create user+device first.
    headers = _auth_headers(client)
    client.post("/users", json={"full_name": "Obs User"}, headers=headers)
    client.post(
        "/devices",
        json={
            "user_id": 1,
            "device_code": "obs-device-001",
            "device_name": "Obs Device",
            "is_active": True,
        },
        headers=headers,
    )
    response = client.post(
        "/events",
        json={
            "schema_version": "1.0",
            "trace_id": str(uuid.uuid4()),
            "device_code": "obs-device-001",
            "event_type": "fall",
            "severity": "high",
            "source": "test",
        },
        headers={"X-Device-Token": "definitely-wrong-token"},
    )
    assert response.status_code == 401
    _assert_error_envelope(response.json(), 401, "unauthorized")


def test_422_returns_consistent_error_format(client: TestClient) -> None:
    """Sending an invalid payload to /auth/login returns 422 in error envelope."""
    response = client.post("/auth/login", json={"bad_field": "x"})
    assert response.status_code == 422
    body = response.json()
    _assert_error_envelope(body, 422, "validation_error")


def test_422_order_invalid_contains_request_id(client: TestClient) -> None:
    """422 for invalid order param has request_id in body."""
    response = client.get("/events", params={"order": "invalid"}, headers=_auth_headers(client))
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 422
    assert body.get("request_id") == response.headers.get("x-request-id")


# ---------------------------------------------------------------------------
# 3.  request_id roundtrip — body matches header
# ---------------------------------------------------------------------------


def test_error_body_request_id_matches_response_header(client: TestClient) -> None:
    """The request_id in the error body must equal the X-Request-ID response header."""
    custom_id = "trace-roundtrip-999"
    response = client.get(
        "/events",
        headers={"X-Request-ID": custom_id},
        # no auth — will 401
    )
    assert response.status_code == 401
    assert response.headers["x-request-id"] == custom_id
    assert response.json()["request_id"] == custom_id


# ---------------------------------------------------------------------------
# 4.  Unhandled exceptions → 500
# ---------------------------------------------------------------------------


def test_unhandled_exception_returns_500_with_envelope(client: TestClient) -> None:
    """An endpoint that raises an unexpected exception must return 500 in the error envelope."""
    # Temporarily mount a broken route on the app.
    test_router_app: FastAPI = app

    @test_router_app.get("/test-crash-endpoint-do-not-use")
    def _crash() -> None:
        raise RuntimeError("deliberate test crash")

    try:
        response = client.get("/test-crash-endpoint-do-not-use")
        assert response.status_code == 500
        body = response.json()
        _assert_error_envelope(body, 500, "internal_server_error")
        # Must NOT leak internal details.
        assert "deliberate test crash" not in body["message"]
        assert "RuntimeError" not in body["message"]
    finally:
        # Remove the route to avoid polluting other tests.
        test_router_app.routes[:] = [
            r for r in test_router_app.routes
            if getattr(r, "path", None) != "/test-crash-endpoint-do-not-use"
        ]


def test_500_response_has_x_request_id_header(client: TestClient) -> None:
    """500 responses must carry X-Request-ID in the response header.

    This is a non-trivial case: the exception bypasses RequestIDMiddleware's
    post-processing, so unhandled_exception_handler sets the header explicitly.
    """
    test_router_app: FastAPI = app

    @test_router_app.get("/test-crash-header-check")
    def _crash2() -> None:
        raise RuntimeError("header check crash")

    try:
        custom_id = "trace-500-header-check"
        response = client.get("/test-crash-header-check", headers={"X-Request-ID": custom_id})
        assert response.status_code == 500
        assert response.headers.get("x-request-id") == custom_id
        assert response.json()["request_id"] == custom_id
    finally:
        test_router_app.routes[:] = [
            r for r in test_router_app.routes
            if getattr(r, "path", None) != "/test-crash-header-check"
        ]


# ---------------------------------------------------------------------------
# 5.  Normal endpoints not broken
# ---------------------------------------------------------------------------


def test_health_endpoint_still_works(client: TestClient) -> None:
    """The health endpoint must return 200 and correct JSON after paso 6."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body


def test_login_still_works(client: TestClient) -> None:
    """Login endpoint must still return a bearer token with the error handlers in place."""
    response = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_credentials_returns_401_envelope(client: TestClient) -> None:
    response = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401
    _assert_error_envelope(response.json(), 401, "unauthorized")


# ---------------------------------------------------------------------------
# 6.  X-Request-ID header present for every error status code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status_code,path,method,kwargs", [
    (404, "/no-such-path", "get", {}),
    (405, "/health", "post", {}),  # wrong method on existing route
])
def test_error_x_request_id_header_always_present(
    client: TestClient,
    status_code: int,
    path: str,
    method: str,
    kwargs: dict,
) -> None:
    """X-Request-ID must be present in the response header for all error status codes."""
    fn = getattr(client, method)
    response = fn(path, headers=_auth_headers(client), **kwargs)
    assert response.status_code == status_code
    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"]


# ---------------------------------------------------------------------------
# 7.  Secrets must not appear in logs
# ---------------------------------------------------------------------------


def test_log_does_not_expose_authorization_token(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """The raw JWT value must never appear in log output."""
    token = _login(client)
    with caplog.at_level(logging.INFO, logger="app.core.middleware"):
        client.get("/health", headers={"Authorization": f"Bearer {token}"})

    all_log_text = " ".join(r.getMessage() for r in caplog.records)
    assert token not in all_log_text, "JWT access token must not appear in log output"


def test_log_does_not_expose_device_token(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """The raw X-Device-Token value must never appear in log output."""
    secret_token = "super-secret-device-token-xyz-should-never-appear-in-logs"
    with caplog.at_level(logging.INFO, logger="app.core.middleware"):
        # The request will fail (401/403/404) but that’s irrelevant —
        # we only care that the token value doesn’t leak into the log.
        client.post(
            "/events",
            json={
                "schema_version": "1.0",
                "trace_id": str(uuid.uuid4()),
                "device_code": "some-device",
                "event_type": "fall",
                "severity": "high",
                "source": "test",
            },
            headers={"X-Device-Token": secret_token},
        )

    all_log_text = " ".join(r.getMessage() for r in caplog.records)
    assert secret_token not in all_log_text, "Device token must not appear in log output"
