"""Row helpers shared by the API and views."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from . import clock
from .checkout_gate import GateInput
from .catalog import warning_digest
from .errors import ApiError


def owned_session(conn: sqlite3.Connection, session_id: str, owner_hash: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM sessions WHERE id=? AND owner_hash=?", (session_id, owner_hash)).fetchone()
    if row is None:  # 404 for both "missing" and "not yours" so IDs cannot be probed
        raise ApiError(404, "session_not_found", "Session not found.")
    return row


def contact_flag(conn: sqlite3.Connection, session_id: str) -> datetime | None:
    row = conn.execute("SELECT MIN(verdict_at) AS t FROM reviews WHERE session_id=? AND verdict='suspected_scam'", (session_id,)).fetchone()
    return clock.parse(row["t"]) if row and row["t"] else None


def gate_input(row: sqlite3.Row, flagged_at: datetime | None) -> GateInput:
    return GateInput(
        status=row["status"], risk_level=row["risk_level"], risk_score=row["risk_score"],
        created_at=clock.parse(row["created_at"]), expires_at=clock.parse(row["expires_at"]),
        warning_digest=warning_digest(),
        ack_at=clock.parse(row["ack_at"]) if row["ack_at"] else None,
        ack_digest=row["ack_digest"], ack_risk_score=row["ack_risk_score"],
        contact_flagged_scam=flagged_at is not None, contact_flagged_at=flagged_at,
    )


def stored_signals(row: sqlite3.Row) -> dict:
    return json.loads(row["signals_json"])
