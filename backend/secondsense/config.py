"""Environment-driven settings with fail-closed validation. No secret is ever logged or returned."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

SANDBOX_HOST = "api-m.sandbox.paypal.com"


class ConfigError(RuntimeError):
    pass


def _int(name: str, default: int, lo: int, hi: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if not lo <= value <= hi:
        raise ConfigError(f"{name} must be between {lo} and {hi}")
    return value


def parse_origins(raw: str) -> tuple[str, ...]:
    origins = []
    for item in (p.strip() for p in raw.split(",")):
        if not item:
            continue
        if item == "*" or "*" in item:
            raise ConfigError("ALLOWED_ORIGINS must list explicit origins; wildcards are not allowed")
        parsed = urlparse(item)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ConfigError(f"Invalid origin in ALLOWED_ORIGINS: {item!r} (expected scheme://host[:port])")
        origins.append(f"{parsed.scheme}://{parsed.netloc}")
    if not origins:
        raise ConfigError("ALLOWED_ORIGINS must contain at least one origin")
    return tuple(origins)


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    allowed_origins: tuple[str, ...] = ("http://localhost:3000",)
    database_path: Path = Path("data/secondsense.db")
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    paypal_base_url: str = f"https://{SANDBOX_HOST}"
    paypal_merchant_id: str | None = None
    session_ttl_seconds: int = 1800
    order_capture_window_seconds: int = 1800
    high_risk_min_pause_seconds: int = 20
    ack_valid_seconds: int = 600
    review_ttl_seconds: int = 86400
    max_reviews_per_session: int = 3
    capture_retry_after_seconds: int = 30
    rate_limit_per_minute: int = 30

    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_client_secret)

    @property
    def paypal_environment(self) -> str:
        return "sandbox" if urlparse(self.paypal_base_url).hostname == SANDBOX_HOST else "live"

    @classmethod
    def from_env(cls) -> "Settings":
        base = os.getenv("PAYPAL_BASE_URL", f"https://{SANDBOX_HOST}").rstrip("/")
        host = urlparse(base).hostname
        if host != SANDBOX_HOST and os.getenv("PAYPAL_ALLOW_NON_SANDBOX", "").lower() != "true":
            raise ConfigError(
                "PAYPAL_BASE_URL is not the PayPal Sandbox host. This prototype is sandbox-only; "
                "refusing to start (set PAYPAL_ALLOW_NON_SANDBOX=true only after a security review)."
            )
        origins_raw = os.getenv("ALLOWED_ORIGINS") or os.getenv("ALLOWED_ORIGIN") or "http://localhost:3000"
        return cls(
            app_env=os.getenv("APP_ENV", "development").lower(),
            allowed_origins=parse_origins(origins_raw),
            database_path=Path(os.getenv("DATABASE_PATH", "data/secondsense.db")),
            paypal_client_id=os.getenv("PAYPAL_CLIENT_ID") or None,
            paypal_client_secret=os.getenv("PAYPAL_CLIENT_SECRET") or None,
            paypal_base_url=base,
            paypal_merchant_id=os.getenv("PAYPAL_MERCHANT_ID") or None,
            session_ttl_seconds=_int("SESSION_TTL_SECONDS", 1800, 60, 86400),
            order_capture_window_seconds=_int("ORDER_CAPTURE_WINDOW_SECONDS", 1800, 60, 86400),
            high_risk_min_pause_seconds=_int("HIGH_RISK_MIN_PAUSE_SECONDS", 20, 0, 600),
            ack_valid_seconds=_int("ACK_VALID_SECONDS", 600, 30, 3600),
            review_ttl_seconds=_int("REVIEW_TTL_SECONDS", 86400, 300, 604800),
            max_reviews_per_session=_int("MAX_REVIEWS_PER_SESSION", 3, 1, 10),
            capture_retry_after_seconds=_int("CAPTURE_RETRY_AFTER_SECONDS", 30, 5, 600),
            rate_limit_per_minute=_int("RATE_LIMIT_PER_MINUTE", 30, 1, 1000),
        )
