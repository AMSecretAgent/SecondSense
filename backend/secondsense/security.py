"""Token hashing, owner-key validation and a small in-process rate limiter."""
from __future__ import annotations

import hashlib
import re
import secrets
import threading
import time
from collections import defaultdict, deque

from .errors import ApiError

OWNER_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def owner_hash_from_header(value: str | None) -> str:
    """The browser-held owner key scopes sessions to one browser. It is NOT end-user authentication."""
    if not value or not OWNER_KEY_RE.fullmatch(value):
        raise ApiError(401, "owner_key_required", "A valid X-Owner-Key header is required.")
    return hash_token(value)


class RateLimiter:
    """Sliding-window limiter, per process. Replace with a shared store (e.g. Redis) when scaling out."""

    def __init__(self, limit_per_minute: int):
        self.limit = limit_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.limit:
                retry = max(1, int(60 - (now - hits[0])))
                raise ApiError(429, "rate_limited", "Too many requests. Please slow down.", retry_after_seconds=retry)
            hits.append(now)
