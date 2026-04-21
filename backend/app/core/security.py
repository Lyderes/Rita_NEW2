from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"
PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 390000


def verify_frontend_credentials(username: str, password: str) -> bool:
    settings = get_settings()
    return hmac.compare_digest(username, settings.frontend_username) and hmac.compare_digest(
        password,
        settings.frontend_password,
    )


def hash_password(password: str) -> str:
    salt = token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        PASSWORD_HASH_ITERATIONS,
    )
    encoded = base64.urlsafe_b64encode(digest).decode()
    return f"{PASSWORD_HASH_SCHEME}${PASSWORD_HASH_ITERATIONS}${salt}${encoded}"


def verify_password(password: str, stored_hash: str) -> bool:
    parts = stored_hash.split("$", 3)
    if len(parts) != 4:
        return False

    scheme, iterations_raw, salt, expected_hash = parts
    if scheme != PASSWORD_HASH_SCHEME:
        return False

    try:
        iterations = int(iterations_raw)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        iterations,
    )
    computed = base64.urlsafe_b64encode(digest).decode()
    return hmac.compare_digest(computed, expected_hash)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


import logging

logger = logging.getLogger(__name__)

def decode_access_token(token: str) -> dict[str, object]:
    settings = get_settings()
    # Diagnostic for "Invalid bearer token" audit
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except Exception as e:
        logger.error(f"JWT Decode failed. Secret(start): {settings.secret_key[:5]}... Token(start): {token[:10]}... Error: {str(e)}")
        raise e


def generate_device_token() -> str:
    """Generate a cryptographically random plain-text device token (192-bit entropy)."""
    return token_urlsafe(24)


def hash_device_token(plain_token: str) -> str:
    """Return SHA-256 hex digest of the plain token for safe storage."""
    return hashlib.sha256(plain_token.encode()).hexdigest()


def verify_device_token(stored_hash: str | None, provided_token: str) -> bool:
    """Compare the SHA-256 hash of the provided token against the stored hash."""
    if not stored_hash:
        return False
    expected = hash_device_token(provided_token)
    return hmac.compare_digest(stored_hash, expected)
