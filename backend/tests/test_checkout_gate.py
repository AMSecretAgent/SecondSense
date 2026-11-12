"""Checkout gate: pure-function tests with an explicit clock."""
from datetime import datetime, timedelta, timezone

import pytest

from secondsense import checkout_gate as g

T0 = datetime(2026, 11, 12, 12, 0, 0, tzinfo=timezone.utc)
CFG = g.GateConfig(min_pause_seconds=20, ack_valid_seconds=600)
DIGEST = "d" * 32


def mk(**kw):
    base = dict(status=g.ANALYZED, risk_level="low", risk_score=10, created_at=T0, expires_at=T0 + timedelta(minutes=30), warning_digest=DIGEST)
    base.update(kw)
    return g.GateInput(**base)


def high(**kw):
    return mk(risk_level="high", risk_score=95, **kw)


def after(s):
    return T0 + timedelta(seconds=s)


# --- risk-driven decisions -----------------------------------------------------------------------------------------
def test_low_and_review_proceed_without_acknowledgment():
    for level in ("low", "review"):
        d = g.evaluate_order_creation(mk(risk_level=level), after(1), CFG)
        assert d.allowed and d.code == g.ALLOWED and not d.ack_required


def test_high_without_acknowledgment_is_blocked():
    d = g.evaluate_order_creation(high(), after(300), CFG)
    assert not d.allowed and d.code == g.ACK_REQUIRED and d.ack_required


def test_high_with_bound_fresh_acknowledgment_is_allowed():
    d = g.evaluate_order_creation(high(ack_at=after(25), ack_digest=DIGEST, ack_risk_score=95), after(60), CFG)
    assert d.allowed and d.effective_level == "high"


def test_acknowledgment_for_a_different_warning_or_score_is_rejected():
    wrong_digest = high(ack_at=after(25), ack_digest="x" * 32, ack_risk_score=95)
    wrong_score = high(ack_at=after(25), ack_digest=DIGEST, ack_risk_score=70)
    for gi in (wrong_digest, wrong_score):
        d = g.evaluate_order_creation(gi, after(60), CFG)
        assert not d.allowed and d.code == g.ACK_STALE


def test_acknowledgment_expires_for_order_creation_but_not_for_capture():
    gi = high(ack_at=after(25), ack_digest=DIGEST, ack_risk_score=95)
    late = after(25 + CFG.ack_valid_seconds + 1)
    assert g.evaluate_order_creation(gi, late, CFG).code == g.ACK_EXPIRED
    ready = high(status=g.ORDER_CREATED, ack_at=after(25), ack_digest=DIGEST, ack_risk_score=95, expires_at=late + timedelta(minutes=5))
    assert g.evaluate_capture(ready, late, CFG).allowed


def test_session_expiry_blocks_everything():
    gi = mk(expires_at=after(100))
    assert g.evaluate_order_creation(gi, after(100), CFG).code == g.SESSION_EXPIRED
    assert g.evaluate_capture(mk(status=g.ORDER_CREATED, expires_at=after(100)), after(101), CFG).code == g.SESSION_EXPIRED


# --- trusted-contact verdicts only escalate ------------------------------------------------------------------------
@pytest.mark.parametrize("level", ["low", "review"])
def test_contact_scam_flag_escalates_to_high_friction(level):
    gi = mk(risk_level=level, contact_flagged_scam=True, contact_flagged_at=after(5))
    assert g.effective_level(gi) == "high"
    d = g.evaluate_order_creation(gi, after(60), CFG)
    assert not d.allowed and d.code == g.ACK_REQUIRED


def test_contact_flag_after_order_creation_blocks_capture_until_acknowledged():
    gi = mk(status=g.ORDER_CREATED, risk_level="review", contact_flagged_scam=True, contact_flagged_at=after(50))
    assert g.evaluate_capture(gi, after(60), CFG).code == g.ACK_REQUIRED


def test_gate_input_has_no_way_to_lower_the_level():
    # There is intentionally no "safe verdict" or client "acknowledged" field to pass in.
    assert "safe" not in " ".join(g.GateInput.__dataclass_fields__)
    assert g.effective_level(high()) == "high"


# --- state machine: no duplicate orders, no repeated capture --------------------------------------------------------
@pytest.mark.parametrize("status,code", [
    (g.ORDER_CREATED, g.ORDER_EXISTS), (g.CAPTURE_PENDING, g.ORDER_EXISTS), (g.NEEDS_RECONCILIATION, g.ORDER_EXISTS),
    (g.ORDER_CREATING, g.ORDER_BUSY), (g.CAPTURED, g.ALREADY_CAPTURED), ("weird", g.INVALID_STATE)])
def test_order_creation_requires_analyzed_state(status, code):
    assert g.evaluate_order_creation(mk(status=status), after(1), CFG).code == code


def test_capture_requires_an_existing_order_and_never_repeats():
    assert g.evaluate_capture(mk(status=g.ANALYZED), after(1), CFG).code == g.NO_ORDER
    assert g.evaluate_capture(mk(status=g.CAPTURED), after(1), CFG).code == g.ALREADY_CAPTURED
    assert g.evaluate_capture(mk(status=g.ORDER_CREATED), after(1), CFG).allowed
    assert g.evaluate_capture(mk(status=g.CAPTURE_PENDING), after(1), CFG).allowed  # retry path; guarded by CAS + idempotency key


# --- acknowledgment transition --------------------------------------------------------------------------------------
def test_acknowledgment_requires_the_server_measured_pause():
    early = g.evaluate_acknowledgment(high(), DIGEST, after(5), CFG)
    assert not early.allowed and early.pause_remaining_seconds == 15
    assert g.evaluate_acknowledgment(high(), DIGEST, after(20), CFG).allowed


def test_acknowledgment_must_present_the_issued_warning_digest():
    d = g.evaluate_acknowledgment(high(), "nope", after(60), CFG)
    assert not d.allowed and d.code == g.ACK_STALE


def test_acknowledgment_not_recordable_for_low_risk_or_after_order():
    assert g.evaluate_acknowledgment(mk(), DIGEST, after(60), CFG).code == g.INVALID_STATE
    assert g.evaluate_acknowledgment(high(status=g.ORDER_CREATED), DIGEST, after(60), CFG).code == g.INVALID_STATE
    assert g.evaluate_acknowledgment(high(expires_at=after(30)), DIGEST, after(60), CFG).code == g.SESSION_EXPIRED


def test_pause_clock_restarts_when_a_contact_flag_causes_the_escalation():
    gi = mk(risk_level="review", contact_flagged_scam=True, contact_flagged_at=after(100))
    assert g.evaluate_acknowledgment(gi, DIGEST, after(105), CFG).pause_remaining_seconds == 15
    assert g.evaluate_acknowledgment(gi, DIGEST, after(121), CFG).allowed
