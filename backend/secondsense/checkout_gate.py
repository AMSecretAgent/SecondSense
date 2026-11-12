"""Authoritative server-side checkout gate. Pure functions: state in, decision out (no I/O, no clock).

Rules
  * The risk level is computed and stored by the server at analysis time. Clients cannot supply it.
  * A trusted-contact verdict can only ESCALATE friction ("suspected_scam" -> treated as high). A "safe"
    verdict never lowers it, so a coerced or malicious "contact" cannot unlock a paused checkout.
  * HIGH requires a recorded acknowledgment that is (a) bound to this session, (b) bound to the exact warning
    text the user was shown (digest), (c) made after a server-measured minimum pause, and (d) fresh
    when the order is created.
  * Order creation and capture additionally require legal session state, so orders cannot be duplicated
    and a captured session cannot be captured again.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# session statuses
ANALYZED = "analyzed"
ORDER_CREATING = "order_creating"
ORDER_CREATED = "order_created"
CAPTURE_PENDING = "capture_pending"
CAPTURED = "captured"
NEEDS_RECONCILIATION = "needs_reconciliation"

_RANK = {"low": 0, "review": 1, "high": 2}

# decision codes
ALLOWED = "allowed"
SESSION_EXPIRED = "session_expired"
ACK_REQUIRED = "acknowledgment_required"
ACK_EXPIRED = "acknowledgment_expired"
ACK_STALE = "acknowledgment_stale"
ORDER_EXISTS = "order_already_created"
ORDER_BUSY = "order_in_progress"
ALREADY_CAPTURED = "already_captured"
INVALID_STATE = "invalid_state"
NO_ORDER = "no_order"


@dataclass(frozen=True)
class GateConfig:
    min_pause_seconds: int = 20
    ack_valid_seconds: int = 600


@dataclass(frozen=True)
class GateInput:
    status: str
    risk_level: str
    risk_score: int
    created_at: datetime
    expires_at: datetime
    warning_digest: str            # digest of the warning the server currently issues for this session
    ack_at: datetime | None = None
    ack_digest: str | None = None
    ack_risk_score: int | None = None
    contact_flagged_scam: bool = False
    contact_flagged_at: datetime | None = None


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    code: str
    message: str
    effective_level: str
    ack_required: bool = False
    pause_remaining_seconds: int = 0


def effective_level(g: GateInput) -> str:
    if g.contact_flagged_scam and _RANK[g.risk_level] < _RANK["high"]:
        return "high"
    return g.risk_level


def pause_started_at(g: GateInput) -> datetime:
    """The pause clock starts when HIGH friction began: analysis time, or the contact flag if that escalated it."""
    if g.risk_level != "high" and g.contact_flagged_scam and g.contact_flagged_at:
        return g.contact_flagged_at
    return g.created_at


def pause_remaining(g: GateInput, now: datetime, cfg: GateConfig) -> int:
    end = pause_started_at(g) + timedelta(seconds=cfg.min_pause_seconds)
    return max(0, int((end - now).total_seconds() + 0.999))


def evaluate_risk_gate(g: GateInput, now: datetime, cfg: GateConfig, *, ack_must_be_fresh: bool) -> GateDecision:
    eff = effective_level(g)
    if now >= g.expires_at:
        return GateDecision(False, SESSION_EXPIRED, "This checkout session has expired. Start a new analysis.", eff)
    if eff != "high":
        return GateDecision(True, ALLOWED, "Checkout may proceed.", eff)
    remaining = pause_remaining(g, now, cfg)
    if g.ack_at is None:
        return GateDecision(False, ACK_REQUIRED,
                            "High-risk checkout is paused until you review and acknowledge the warning.",
                            eff, ack_required=True, pause_remaining_seconds=remaining)
    if g.ack_digest != g.warning_digest or g.ack_risk_score != g.risk_score:
        return GateDecision(False, ACK_STALE, "The recorded acknowledgment does not match the current warning. Review it again.",
                            eff, ack_required=True, pause_remaining_seconds=remaining)
    if ack_must_be_fresh and now - g.ack_at > timedelta(seconds=cfg.ack_valid_seconds):
        return GateDecision(False, ACK_EXPIRED, "Your acknowledgment has expired. Review the warning again.",
                            eff, ack_required=True, pause_remaining_seconds=remaining)
    return GateDecision(True, ALLOWED, "High-risk warning acknowledged; checkout may proceed.", eff)


def evaluate_order_creation(g: GateInput, now: datetime, cfg: GateConfig) -> GateDecision:
    eff = effective_level(g)
    if g.status == CAPTURED:
        return GateDecision(False, ALREADY_CAPTURED, "This session has already been captured.", eff)
    if g.status in (ORDER_CREATED, CAPTURE_PENDING, NEEDS_RECONCILIATION):
        return GateDecision(False, ORDER_EXISTS, "An order already exists for this session.", eff)
    if g.status == ORDER_CREATING:
        return GateDecision(False, ORDER_BUSY, "An order is already being created for this session.", eff)
    if g.status != ANALYZED:
        return GateDecision(False, INVALID_STATE, "Session is not in a state that allows order creation.", eff)
    return evaluate_risk_gate(g, now, cfg, ack_must_be_fresh=True)


def evaluate_capture(g: GateInput, now: datetime, cfg: GateConfig) -> GateDecision:
    eff = effective_level(g)
    if g.status == CAPTURED:
        return GateDecision(False, ALREADY_CAPTURED, "This session has already been captured.", eff)
    if g.status not in (ORDER_CREATED, CAPTURE_PENDING):
        return GateDecision(False, NO_ORDER, "No approved order is awaiting capture for this session.", eff)
    # Ack freshness is enforced at order creation; at capture we require only that the ack still exists
    # and matches (this catches a contact escalation that happened after the order was created).
    return evaluate_risk_gate(g, now, cfg, ack_must_be_fresh=False)


def evaluate_acknowledgment(g: GateInput, presented_digest: str, now: datetime, cfg: GateConfig) -> GateDecision:
    """May an acknowledgment be recorded right now?"""
    eff = effective_level(g)
    if now >= g.expires_at:
        return GateDecision(False, SESSION_EXPIRED, "This checkout session has expired.", eff)
    if g.status != ANALYZED:
        return GateDecision(False, INVALID_STATE, "Acknowledgment is only possible before an order is created.", eff)
    if eff != "high":
        return GateDecision(False, INVALID_STATE, "This session does not require an acknowledgment.", eff)
    if presented_digest != g.warning_digest:
        return GateDecision(False, ACK_STALE, "The acknowledgment does not match the warning issued for this session.", eff, ack_required=True)
    remaining = pause_remaining(g, now, cfg)
    if remaining > 0:
        return GateDecision(False, ACK_REQUIRED, "Please take the full pause before continuing.", eff,
                            ack_required=True, pause_remaining_seconds=remaining)
    return GateDecision(True, ALLOWED, "Acknowledgment may be recorded.", eff)
