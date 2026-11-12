"""PayPal Orders v2 client (REST, server-side). Secrets stay here; PayPal error bodies are never forwarded."""
from __future__ import annotations

import base64
import threading
import time
from typing import Any, Protocol

import httpx

from .config import Settings


class PayPalError(Exception):
    def __init__(self, code: str, message: str, *, paypal_status: int | None = None, issue: str | None = None,
                 debug_id: str | None = None, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.paypal_status = paypal_status
        self.issue = issue
        self.debug_id = debug_id
        self.http_status = http_status or (503 if code == "paypal_not_configured" else 502)


class PaymentGateway(Protocol):
    def create_order(self, *, amount: str, currency: str, reference_id: str, custom_id: str, description: str,
                     idempotency_key: str, payee_merchant_id: str | None) -> dict[str, Any]: ...
    def get_order(self, order_id: str) -> dict[str, Any]: ...
    def capture_order(self, order_id: str, *, idempotency_key: str) -> dict[str, Any]: ...


class PayPalGateway:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.s = settings
        self.http = client or httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))
        self._token: str | None = None
        self._expires = 0.0
        self._lock = threading.Lock()

    def _access_token(self) -> str:
        if not self.s.paypal_configured:
            raise PayPalError("paypal_not_configured", "PayPal Sandbox credentials are not configured on the server.")
        with self._lock:
            if self._token and time.monotonic() < self._expires - 60:
                return self._token
            basic = base64.b64encode(f"{self.s.paypal_client_id}:{self.s.paypal_client_secret}".encode()).decode()
            try:
                r = self.http.post(f"{self.s.paypal_base_url}/v1/oauth2/token", content=b"grant_type=client_credentials",
                                   headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"})
            except httpx.HTTPError:
                raise PayPalError("paypal_unreachable", "Could not reach PayPal.")
            if r.status_code != 200:
                raise PayPalError("paypal_auth_failed", "PayPal rejected the server credentials.", paypal_status=r.status_code)
            try:
                data = r.json()
                self._token = str(data["access_token"])
                self._expires = time.monotonic() + float(data.get("expires_in", 300))
            except (ValueError, KeyError, TypeError):
                raise PayPalError("paypal_bad_response", "PayPal returned an unexpected token response.")
            return self._token

    def _request(self, method: str, path: str, *, json_body: dict | None = None, request_id: str | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        try:
            r = self.http.request(method, f"{self.s.paypal_base_url}{path}", headers=headers, json=json_body)
        except httpx.HTTPError:
            raise PayPalError("paypal_unreachable", "Could not reach PayPal.")
        if r.status_code >= 400:
            issue = debug = None
            try:  # only whitelisted identifiers are kept; message/description text is dropped
                body = r.json()
                debug = body.get("debug_id")
                details = body.get("details") or []
                issue = details[0].get("issue") if details and isinstance(details[0], dict) else None
            except (ValueError, AttributeError):
                pass
            raise PayPalError("paypal_request_failed", "PayPal rejected the request.", paypal_status=r.status_code,
                              issue=issue if isinstance(issue, str) else None, debug_id=debug if isinstance(debug, str) else None)
        try:
            data = r.json()
        except ValueError:
            raise PayPalError("paypal_bad_response", "PayPal returned an unreadable response.", paypal_status=r.status_code)
        if not isinstance(data, dict):
            raise PayPalError("paypal_bad_response", "PayPal returned an unexpected response.", paypal_status=r.status_code)
        return data

    def create_order(self, *, amount, currency, reference_id, custom_id, description, idempotency_key, payee_merchant_id):
        unit: dict[str, Any] = {"reference_id": reference_id, "custom_id": custom_id, "description": description[:127],
                                "amount": {"currency_code": currency, "value": amount}}
        if payee_merchant_id:
            unit["payee"] = {"merchant_id": payee_merchant_id}
        return self._request("POST", "/v2/checkout/orders", json_body={"intent": "CAPTURE", "purchase_units": [unit]},
                             request_id=idempotency_key)

    def get_order(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v2/checkout/orders/{order_id}")

    def capture_order(self, order_id: str, *, idempotency_key: str) -> dict[str, Any]:
        return self._request("POST", f"/v2/checkout/orders/{order_id}/capture", json_body={}, request_id=idempotency_key)
