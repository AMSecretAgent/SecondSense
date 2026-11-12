"""End-to-end API behaviour against a FAKE gateway (test double). Nothing here exercises real PayPal."""
import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from secondsense.api import create_app
from secondsense.config import ConfigError, Settings, parse_origins
from secondsense.paypal_gateway import PayPalError

from conftest import COERCIVE, H, LEGIT_URGENCY, OTHER_OWNER, OWNER, REVIEW_LEVEL, ack, analyze, capture, order


def paid_session(client, gateway, text="Pay $35 for coffee.", item="coffee"):
    sid = analyze(client, text, item).json()["session_id"]
    oid = order(client, sid).json()["id"]
    gateway.approve(oid)
    return sid, oid


def high_session(client, item="safety_transfer"):
    body = analyze(client, COERCIVE, item).json()
    assert body["risk"]["level"] == "high" and body["gate"]["ack_required"]
    return body


# ---------------------------------------------------------------- authoritative risk gate
def test_client_cannot_bypass_high_risk_with_acknowledged_flag(client, gateway):
    body = high_session(client)
    sid = body["session_id"]
    r = client.post("/api/paypal/orders", json={"session_id": sid, "acknowledged_risk": True}, headers=H)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"   # legacy flag no longer exists
    r = order(client, sid)
    assert r.status_code == 403 and r.json()["error"]["code"] == "acknowledgment_required"
    assert gateway.create_calls == 0


def test_explicit_acknowledgment_transition_is_bound_paused_and_audited(client, gateway, clk):
    body = high_session(client)
    sid, digest = body["session_id"], body["warning"]["digest"]
    early = ack(client, sid, digest)                                   # server measures the pause; the client cannot skip it
    assert early.status_code == 409 and early.json()["error"]["code"] == "pause_not_elapsed"
    assert early.json()["error"]["pause_remaining_seconds"] == 20
    assert order(client, sid).status_code == 403
    clk.advance(21)
    assert ack(client, sid, "0" * 32).status_code == 403                # wrong digest (not the warning issued)
    ok = ack(client, sid, digest)
    assert ok.status_code == 200 and ok.json()["gate"]["allowed"] is True
    created = order(client, sid)
    assert created.status_code == 200 and gateway.create_calls == 1
    events = client.get(f"/api/sessions/{sid}/audit", headers=H).json()
    types = [e["event_type"] for e in events["events"]]
    assert events["chain_valid"] is True
    assert types[:1] == ["session_created"] and "acknowledgment_rejected" in types and "high_risk_acknowledged" in types
    assert types.index("high_risk_acknowledged") < types.index("order_created")
    ack_event = next(e for e in events["events"] if e["event_type"] == "high_risk_acknowledged")
    assert ack_event["detail"]["warning_digest"] == digest and ack_event["detail"]["risk_score"] == body["risk"]["score"]


def test_acknowledgment_expires_before_order_creation(client, gateway, clk):
    body = high_session(client)
    clk.advance(21)
    assert ack(client, body["session_id"], body["warning"]["digest"]).status_code == 200
    clk.advance(601)
    r = order(client, body["session_id"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "acknowledgment_expired"


def test_legitimate_urgency_checks_out_without_friction(client, gateway):
    body = analyze(client, LEGIT_URGENCY, "plumber").json()
    assert body["risk"]["level"] == "low" and body["gate"]["allowed"] and body["warning"] is None
    assert order(client, body["session_id"]).status_code == 200


# ---------------------------------------------------------------- trusted contact
def test_contact_safe_verdict_never_unlocks_and_scam_verdict_escalates(client, gateway, clk):
    body = high_session(client)
    sid = body["session_id"]
    tok = client.post("/api/reviews", json={"session_id": sid, "consent": True}, headers=H).json()["review_path"].split("/")[-1]
    assert client.post(f"/api/reviews/{tok}/verdict", json={"verdict": "safe_to_proceed"}).status_code == 200
    assert order(client, sid).status_code == 403                          # "safe" opinion is advisory only

    s2 = analyze(client, "Pay $35 for coffee.", "coffee").json()["session_id"]   # low risk
    t2 = client.post("/api/reviews", json={"session_id": s2, "consent": True}, headers=H).json()["review_path"].split("/")[-1]
    assert client.post(f"/api/reviews/{t2}/verdict", json={"verdict": "suspected_scam"}).status_code == 200
    r = order(client, s2)
    assert r.status_code == 403 and r.json()["error"]["code"] == "acknowledgment_required"
    view = client.get(f"/api/sessions/{s2}", headers=H).json()
    assert view["risk"]["level"] == "low" and view["risk"]["effective_level"] == "high" and view["warning"]["digest"]


def test_contact_flag_after_order_blocks_capture(client, gateway):
    sid = analyze(client, REVIEW_LEVEL, "plumber").json()["session_id"]
    oid = order(client, sid).json()["id"]
    gateway.approve(oid)
    tok = client.post("/api/reviews", json={"session_id": sid, "consent": True}, headers=H).json()["review_path"].split("/")[-1]
    client.post(f"/api/reviews/{tok}/verdict", json={"verdict": "suspected_scam"})
    r = capture(client, sid, oid)
    assert r.status_code == 403 and r.json()["error"]["code"] == "acknowledgment_required"
    assert gateway.capture_calls == 0


def test_review_link_is_consent_based_expiring_revocable_and_single_verdict(client, clk):
    sid = analyze(client, COERCIVE, "safety_transfer").json()["session_id"]
    assert client.post("/api/reviews", json={"session_id": sid, "consent": False}, headers=H).json()["error"]["code"] == "consent_required"
    made = client.post("/api/reviews", json={"session_id": sid, "consent": True}, headers=H).json()
    assert "advisory" in made["note"] and "not a PayPal approval" in made["note"]
    tok = made["review_path"].split("/")[-1]
    assert client.get(f"/api/reviews/{tok}").status_code == 200
    assert client.post(f"/api/reviews/{tok}/verdict", json={"verdict": "suspected_scam"}).status_code == 200
    assert client.post(f"/api/reviews/{tok}/verdict", json={"verdict": "safe_to_proceed"}).json()["error"]["code"] == "verdict_already_submitted"
    assert client.post(f"/api/reviews/{made['review_id']}/revoke", headers=H).status_code == 200
    assert client.get(f"/api/reviews/{tok}").status_code == 410
    assert client.post(f"/api/reviews/{made['review_id']}/revoke", headers={"X-Owner-Key": OTHER_OWNER}).status_code == 404
    m2 = client.post("/api/reviews", json={"session_id": sid, "consent": True}, headers=H).json()
    t2 = m2["review_path"].split("/")[-1]
    clk.advance(86401)
    assert client.get(f"/api/reviews/{t2}").status_code == 410
    assert client.get("/api/reviews/" + "z" * 43).status_code == 404


def test_review_link_count_is_limited(client):
    sid = analyze(client, "Pay $35 for coffee.").json()["session_id"]
    for _ in range(3):
        assert client.post("/api/reviews", json={"session_id": sid, "consent": True}, headers=H).status_code == 200
    assert client.post("/api/reviews", json={"session_id": sid, "consent": True}, headers=H).json()["error"]["code"] == "review_limit_reached"


# ---------------------------------------------------------------- price / merchant / state integrity
def test_amount_currency_and_item_are_server_side_only(client, gateway):
    for extra in ({"amount": "0.01"}, {"currency": "EUR"}, {"amount": "9999.00", "currency": "USD"}):
        assert client.post("/api/paypal/orders", json={"session_id": "x" * 22, **extra}, headers=H).status_code == 422
    assert client.post("/api/analyze", json={"context": "hello world", "checkout_item_id": "coffee", "amount": "1.00"}, headers=H).status_code == 422
    assert analyze(client, "hello world", "does_not_exist").json()["error"]["code"] == "unknown_checkout_item"
    sid = analyze(client, "Pay $1 for coffee.", "plumber").json()["session_id"]
    order(client, sid)
    assert gateway.last_create["amount"] == "450.00" and gateway.last_create["currency"] == "USD"   # from the server catalog
    assert gateway.last_create["custom_id"] == sid and gateway.last_create["key"] == f"ss-order-{sid}"


def test_payee_merchant_is_sent_when_configured(make_settings, gateway, clk):
    with TestClient(create_app(make_settings(paypal_merchant_id="MERCHANT123"), gateway)) as c:
        order(c, analyze(c, "Pay $35 for coffee.").json()["session_id"])
    assert gateway.last_create["payee"] == "MERCHANT123"


def test_full_capture_flow_and_no_repeated_capture(client, gateway):
    sid, oid = paid_session(client, gateway)
    assert order(client, sid).json() == {"id": oid, "reused": True}       # re-click returns same order, no second PayPal order
    assert gateway.create_calls == 1
    r = capture(client, sid, oid)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "COMPLETED" and body["capture_id"].startswith("FAKECAP") and body["already_captured"] is False
    assert body["amount"] == "35.00" and body["environment"] == "sandbox"
    again = capture(client, sid, oid)
    assert again.status_code == 200 and again.json()["already_captured"] is True and again.json()["capture_id"] == body["capture_id"]
    assert gateway.capture_calls == 1
    assert order(client, sid).json()["error"]["code"] == "already_captured"
    assert gateway.create_calls == 1


def test_concurrent_captures_hit_paypal_once(client, gateway):
    sid, oid = paid_session(client, gateway)
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda _: capture(client, sid, oid), range(6)))
    assert gateway.capture_calls == 1
    assert all(r.status_code in (200, 409) for r in results) and any(r.status_code == 200 for r in results)


def test_capture_requires_buyer_approval_first(client, gateway):
    sid = analyze(client, "Pay $35 for coffee.").json()["session_id"]
    oid = order(client, sid).json()["id"]
    r = capture(client, sid, oid)                                          # never approved at PayPal
    assert r.status_code == 409 and r.json()["error"]["code"] == "order_status_invalid"
    assert gateway.capture_calls == 0


def test_capture_rejects_amount_tampering_and_foreign_orders(client, gateway):
    gateway.tamper_amount = "1.00"
    sid, oid = paid_session(client, gateway)
    r = capture(client, sid, oid)
    assert r.status_code == 409 and r.json()["error"]["code"] == "order_amount_mismatch" and gateway.capture_calls == 0
    gateway.tamper_amount = None
    a, oa = paid_session(client, gateway)
    b, ob = paid_session(client, gateway)
    r = capture(client, b, oa)                                             # order from session A, presented for session B
    assert r.status_code == 409 and r.json()["error"]["code"] == "order_session_mismatch" and gateway.capture_calls == 0


def test_capture_rejects_order_bound_to_a_different_session_at_paypal(client, gateway):
    sid, oid = paid_session(client, gateway)
    gateway.orders[oid]["purchase_units"][0]["custom_id"] = "someone-else"
    assert capture(client, sid, oid).json()["error"]["code"] == "order_session_mismatch"
    assert gateway.capture_calls == 0


def test_expired_session_cannot_order(client, gateway, clk):
    sid = analyze(client, "Pay $35 for coffee.").json()["session_id"]
    clk.advance(1801)
    r = order(client, sid)
    assert r.status_code == 410 and r.json()["error"]["code"] == "session_expired" and gateway.create_calls == 0


def test_paypal_create_failure_is_sanitized_and_retryable(client, gateway):
    gateway.fail_create = PayPalError("paypal_request_failed", "PayPal rejected the request.", paypal_status=422, issue="INVALID_REQUEST", debug_id="dbg1")
    sid = analyze(client, "Pay $35 for coffee.").json()["session_id"]
    r = order(client, sid)
    assert r.status_code == 502 and r.json()["error"] == {"code": "paypal_request_failed", "message": "PayPal rejected the request.",
                                                          "paypal_issue": "INVALID_REQUEST", "paypal_debug_id": "dbg1"}
    assert client.get(f"/api/sessions/{sid}", headers=H).json()["status"] == "analyzed"
    gateway.fail_create = None
    assert order(client, sid).status_code == 200


def test_lost_capture_response_is_reconciled_from_the_order_without_a_second_capture(client, gateway):
    sid, oid = paid_session(client, gateway)
    gateway.capture_raises = PayPalError("paypal_unreachable", "Could not reach PayPal.")
    gateway.capture_completes_before_raising = True                        # PayPal captured, but the response was lost
    r = capture(client, sid, oid)
    assert r.status_code == 502 and r.json()["error"]["state_unknown"] is True
    assert client.get(f"/api/sessions/{sid}", headers=H).json()["status"] == "capture_pending"
    final = capture(client, sid, oid)                                      # retry: GET shows COMPLETED -> finalize, no new capture
    assert final.status_code == 200 and final.json()["capture_id"].startswith("FAKECAP")
    assert gateway.capture_calls == 1


def test_unknown_outcome_blocks_immediate_retry_then_allows_idempotent_retry(client, gateway, clk):
    sid, oid = paid_session(client, gateway)
    gateway.capture_raises = PayPalError("paypal_unreachable", "Could not reach PayPal.")   # PayPal did NOT capture
    assert capture(client, sid, oid).status_code == 502
    gateway.capture_raises = None
    early = capture(client, sid, oid)                                      # inside the retry window: refuse to double-fire
    assert early.status_code == 409 and early.json()["error"]["code"] == "capture_in_progress"
    assert gateway.capture_calls == 1
    clk.advance(31)
    assert capture(client, sid, oid).status_code == 200 and gateway.capture_calls == 2   # same PayPal-Request-Id guards PayPal-side


def test_definitive_paypal_decline_returns_to_retryable_state(client, gateway):
    sid, oid = paid_session(client, gateway)
    gateway.capture_raises = PayPalError("paypal_request_failed", "PayPal rejected the request.", paypal_status=422, issue="INSTRUMENT_DECLINED")
    r = capture(client, sid, oid)
    assert r.status_code == 502 and "state_unknown" not in r.json()["error"]
    assert client.get(f"/api/sessions/{sid}", headers=H).json()["status"] == "order_created"


# ---------------------------------------------------------------- ownership / auth scoping
def test_sessions_are_scoped_to_the_owner_key(client, gateway):
    sid = analyze(client, "Pay $35 for coffee.").json()["session_id"]
    other = {"X-Owner-Key": OTHER_OWNER}
    assert client.get("/api/sessions").status_code == 401
    assert client.get("/api/sessions", headers={"X-Owner-Key": "short"}).status_code == 401
    assert client.get(f"/api/sessions/{sid}", headers=other).status_code == 404
    assert order(client, sid, headers=other).status_code == 404
    assert client.get("/api/sessions", headers=other).json() == []
    assert [r["session_id"] for r in client.get("/api/sessions", headers=H).json()] == [sid]


# ---------------------------------------------------------------- privacy
def test_raw_message_is_never_stored_shared_echoed_or_logged(client, settings, caplog):
    secret = "ZEBRA-SECRET-PHRASE-93817"
    text = f"PayPal fraud department security alert {secret}: Do not contact support or tell anyone. Move $1200 to our safety account."
    with caplog.at_level(logging.DEBUG):
        body = analyze(client, text, "safety_transfer").json()
        sid = body["session_id"]
        assert any(body["analysis"]["evidence"].values())                     # shown once to the user who typed it
        tok = client.post("/api/reviews", json={"session_id": sid, "consent": True}, headers=H).json()["review_path"].split("/")[-1]
        review = client.get(f"/api/reviews/{tok}").text
        public = [client.get(f"/api/sessions/{sid}", headers=H).text, client.get("/api/sessions", headers=H).text,
                  client.get(f"/api/sessions/{sid}/audit", headers=H).text, review]
        bad = client.post("/api/analyze", json={"context": text, "checkout_item_id": "BAD ITEM"}, headers=H)
    assert bad.status_code == 422 and secret not in bad.text and "input" not in bad.json()["error"]
    for blob in public:
        assert secret not in blob and "safety account" not in blob and "evidence" not in blob
    assert secret not in caplog.text and "safety account" not in caplog.text
    data = b""
    for suffix in ("", "-wal"):
        try:
            data += open(str(settings.database_path) + suffix, "rb").read()
        except FileNotFoundError:
            pass
    assert secret.encode() not in data and b"fraud department" not in data
    assert sqlite3.connect(settings.database_path).execute("SELECT context_chars FROM sessions").fetchone()[0] == len(text)


def test_review_tokens_and_owner_keys_are_stored_only_as_hashes(client, settings):
    sid = analyze(client, "Pay $35 for coffee.").json()["session_id"]
    made = client.post("/api/reviews", json={"session_id": sid, "consent": True}, headers=H).json()
    tok = made["review_path"].split("/")[-1]
    db = sqlite3.connect(settings.database_path)
    stored = " ".join(str(v) for t in ("sessions", "reviews") for row in db.execute(f"SELECT * FROM {t}") for v in row)
    assert tok not in stored and OWNER not in stored


def test_audit_chain_detects_tampering(client, settings):
    sid = analyze(client, "Pay $35 for coffee.").json()["session_id"]
    order(client, sid)
    assert client.get(f"/api/sessions/{sid}/audit", headers=H).json()["chain_valid"] is True
    db = sqlite3.connect(settings.database_path)
    db.execute("UPDATE audit_events SET detail_json='{\"order_id\":\"FORGED\"}' WHERE event_type='order_created'")
    db.commit()
    assert client.get(f"/api/sessions/{sid}/audit", headers=H).json()["chain_valid"] is False


# ---------------------------------------------------------------- config / transport safety
def test_cors_only_allows_configured_origins(client):
    ok = client.options("/api/analyze", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                                                 "Access-Control-Request-Headers": "content-type,x-owner-key"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    evil = client.options("/api/analyze", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in evil.headers
    assert "access-control-allow-credentials" not in ok.headers


def test_config_validation_fails_closed(monkeypatch):
    for bad in ("*", "http://*.example.com", "ftp://x.com", "http://x.com/path", ""):
        with pytest.raises(ConfigError):
            parse_origins(bad)
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://api-m.paypal.com")
    monkeypatch.delenv("PAYPAL_ALLOW_NON_SANDBOX", raising=False)
    with pytest.raises(ConfigError):
        Settings.from_env()


def test_public_config_exposes_no_secret_and_labels_the_flow(make_settings, gateway, clk):
    s = make_settings(paypal_client_id="CID123", paypal_client_secret="TOP-SECRET-VALUE")
    with TestClient(create_app(s, gateway)) as c:
        text = c.get("/api/config").text
        cfg = c.get("/api/config").json()
    assert "TOP-SECRET-VALUE" not in text and cfg["payments"]["client_id"] == "CID123"
    assert cfg["payments"]["environment"] == "sandbox" and "not escrow" in cfg["payments"]["flow"]
    assert cfg["merchant"]["verified"] is False and cfg["risk_engine"]["calibrated"] is False


def test_unconfigured_payments_report_503_not_a_fake_success(make_settings, clk):
    from secondsense.paypal_gateway import PayPalGateway
    s = make_settings()
    with TestClient(create_app(s, PayPalGateway(s))) as c:
        assert c.get("/api/config").json()["payments"] == {**c.get("/api/config").json()["payments"], "configured": False, "client_id": None}
        r = order(c, analyze(c, "Pay $35 for coffee.").json()["session_id"])
    assert r.status_code == 503 and r.json()["error"]["code"] == "paypal_not_configured"


def test_rate_limit_and_security_headers(make_settings, gateway, clk):
    with TestClient(create_app(make_settings(rate_limit_per_minute=3), gateway)) as c:
        codes = [analyze(c, "Pay $35 for coffee.").status_code for _ in range(4)]
        assert codes == [200, 200, 200, 429]
        r = c.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store" and r.headers["referrer-policy"] == "no-referrer"
