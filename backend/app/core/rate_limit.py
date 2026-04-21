from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Single shared limiter instance — uses in-memory storage (sufficient for
# single-process deployments). Key function: client IP via X-Forwarded-For
# or direct connection address.
limiter = Limiter(key_func=get_remote_address)
