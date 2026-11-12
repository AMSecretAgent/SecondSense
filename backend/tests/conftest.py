"""Shared fixtures.

FakeGateway is a TEST DOUBLE used only inside this test suite. It is never wired into the running app,
and nothing it returns may be presented as a real PayPal Sandbox transaction.
"""
from __future__ import annotations

import itertools
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from secondsense import clock
from secondsense.api import create_app
from secondsense.config import Settings
from secondsense.paypal_gateway import PayPalError

OWNER = "A" * 43
OTHER_OWNER = "B" * 43
H = {"X-Owner-Key": OWNER}

LEGIT_URGENCY = "URGENT: burst pipe in the basement, emergency plumber needs payment within 2 hours so the technician can dispatch."
COERCIVE = ("PayPal fraud department security alert: your account will be permanently frozen. Move $1200 to our safety "
            "account within 15 minutes. Do not contact support or tell anyone.")
REVIEW_LEVEL = "PayPal security alert: please verify your account immediately."  # impersonation + urgency -> 'review'


class FakeGateway:
    def __init__(self):
        self.orders: dict[str, dict] = {}
        self.create_calls = 0
        self.capture_calls = 0
        self.last_create: dict | None = None
        self.fail_create: PayPalError | None = None
        self.capture_raises: Exception | None = None
        self.capture_completes_before_raising = False
        self.tamper_amount: str | None = None
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def create_order(self, *, amount, currency, reference_id, custom_id, description, idempotency_key, payee_merchant_id):
        self.create_calls += 1
        self.last_create = dict(amount=amount, currency=currency, custom_id=custom_id, payee=payee_merchant_id, key=idempotency_key)
        if self.fail_create:
            raise self.fail_create
        oid = f"FAKEORDER{next(self._ids):06d}"
        self.orders[oid] = {"id": oid, "intent": "CAPTURE", "status": "CREATED",
                            "purchase_units": [{"custom_id": custom_id, "amount": {"currency_code": currency, "value": self.tamper_amount or amount}}]}
        return {"id": oid, "status": "CREATED"}

    def approve(self, oid):
        self.orders[oid]["status"] = "APPROVED"

    def get_order(self, order_id):
        return self.orders[order_id]

    def _complete(self, oid):
        o = self.orders[oid]
        o["status"] = "COMPLETED"
        unit = o["purchase_units"][0]
        unit["payments"] = {"captures": [{"id": f"FAKECAP{oid[-6:]}", "status": "COMPLETED", "amount": unit["amount"]}]}

    def capture_order(self, order_id, *, idempotency_key):
        with self._lock:
            self.capture_calls += 1
            if self.capture_raises:
                if self.capture_completes_before_raising:
                    self._complete(order_id)
                raise self.capture_raises
            self._complete(order_id)
            return self.orders[order_id]


class ClockCtl:
    def __init__(self):
        self.now = datetime(2026, 11, 12, 12, 0, 0, tzinfo=timezone.utc)

    def advance(self, seconds: float):
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clk(monkeypatch):
    c = ClockCtl()
    monkeypatch.setattr(clock, "utcnow", lambda: c.now)
    return c


@pytest.fixture
def make_settings(tmp_path):
    def _make(**kw):
        base = dict(database_path=Path(tmp_path) / "t.db", rate_limit_per_minute=1000, high_risk_min_pause_seconds=20)
        base.update(kw)
        return Settings(**base)
    return _make


@pytest.fixture
def gateway():
    return FakeGateway()


@pytest.fixture
def settings(make_settings):
    return make_settings()


@pytest.fixture
def client(settings, gateway, clk):
    with TestClient(create_app(settings, gateway)) as c:
        yield c


def analyze(client, context, item="coffee", headers=H):
    return client.post("/api/analyze", json={"context": context, "checkout_item_id": item}, headers=headers)


def ack(client, sid, digest, headers=H):
    return client.post(f"/api/sessions/{sid}/acknowledge", json={"warning_digest": digest, "confirm": True}, headers=headers)


def order(client, sid, headers=H):
    return client.post("/api/paypal/orders", json={"session_id": sid}, headers=headers)


def capture(client, sid, oid, headers=H):
    return client.post(f"/api/paypal/orders/{oid}/capture", json={"session_id": sid}, headers=headers)
