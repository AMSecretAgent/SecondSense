"""Response shaping. Nothing here can include message text; evidence is only attached by /api/analyze."""
from __future__ import annotations

import sqlite3
from typing import Any

from . import catalog, clock, risk_engine, store
from .checkout_gate import GateConfig, evaluate_risk_gate, effective_level, pause_remaining
from .config import Settings

_LABELS = {r.key: r.label for r in risk_engine.RULES}


def _reviews(conn: sqlite3.Connection, session_id: str, now) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT id,created_at,expires_at,revoked_at,verdict,verdict_at FROM reviews WHERE session_id=? ORDER BY created_at", (session_id,)).fetchall()
    return [{"id": r["id"], "created_at": r["created_at"], "expires_at": r["expires_at"],
             "revoked": r["revoked_at"] is not None, "expired": clock.parse(r["expires_at"]) <= now,
             "verdict": r["verdict"], "verdict_at": r["verdict_at"]} for r in rows]


def session_view(conn: sqlite3.Connection, row: sqlite3.Row, settings: Settings) -> dict[str, Any]:
    now = clock.utcnow()
    cfg = GateConfig(settings.high_risk_min_pause_seconds, settings.ack_valid_seconds)
    g = store.gate_input(row, store.contact_flag(conn, row["id"]))
    gate = evaluate_risk_gate(g, now, cfg, ack_must_be_fresh=True)
    eff = effective_level(g)
    signals = {k: {"label": _LABELS.get(k, k), "detected": v["detected"], "points": v["points"]}
               for k, v in store.stored_signals(row).items()}
    warning = None
    if eff == "high":
        warning = {"version": catalog.HIGH_RISK_WARNING_VERSION, "title": catalog.HIGH_RISK_WARNING_TITLE,
                   "points": list(catalog.HIGH_RISK_WARNING_POINTS), "digest": g.warning_digest,
                   "min_pause_seconds": settings.high_risk_min_pause_seconds,
                   "pause_remaining_seconds": pause_remaining(g, now, cfg)}
    return {
        "session_id": row["id"], "status": row["status"], "created_at": row["created_at"], "expires_at": row["expires_at"],
        "checkout": {"item_id": row["item_id"], "label": row["item_label"], "amount": row["amount_value"],
                     "currency": row["currency"], "merchant": catalog.MERCHANT},
        "risk": {"score": row["risk_score"], "level": row["risk_level"], "effective_level": eff, "signals": signals,
                 "explanation": risk_engine.explanation_for(row["risk_level"]), "limitations": risk_engine.LIMITATIONS,
                 "engine_version": risk_engine.ENGINE_VERSION, "scores_are_heuristic": True},
        "gate": {"allowed": gate.allowed, "code": gate.code, "message": gate.message, "ack_required": gate.ack_required,
                 "pause_remaining_seconds": gate.pause_remaining_seconds},
        "warning": warning,
        "reviews": _reviews(conn, row["id"], now),
        "order_id": row["order_id"], "capture_id": row["capture_id"],
    }


def ledger_row(row: sqlite3.Row, flagged: bool) -> dict[str, Any]:
    detected = [k for k, v in store.stored_signals(row).items() if v["detected"]]
    return {
        "session_id": row["id"], "created_at": row["created_at"], "status": row["status"], "risk_score": row["risk_score"],
        "risk_level": row["risk_level"], "effective_level": "high" if flagged and row["risk_level"] != "high" else row["risk_level"],
        "signals": [{"key": k, "label": _LABELS.get(k, k)} for k in detected],
        "item_label": row["item_label"], "amount": row["amount_value"], "currency": row["currency"],
        "acknowledged": row["ack_at"] is not None, "capture_id": row["capture_id"],
    }
