"""Hash-chained audit events per session (tamper-evident, not tamper-proof). Details never contain message text."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from . import clock

GENESIS = "0" * 64


def _hash(prev: str, session_id: str, event_type: str, detail_json: str, created_at: str) -> str:
    return hashlib.sha256("|".join([prev, session_id, event_type, detail_json, created_at]).encode()).hexdigest()


def append(conn: sqlite3.Connection, session_id: str, event_type: str, detail: dict[str, Any]) -> None:
    row = conn.execute("SELECT hash FROM audit_events WHERE session_id=? ORDER BY seq DESC LIMIT 1", (session_id,)).fetchone()
    prev = row["hash"] if row else GENESIS
    detail_json = json.dumps(detail, sort_keys=True, separators=(",", ":"))
    created = clock.iso(clock.utcnow())
    conn.execute("INSERT INTO audit_events (session_id,event_type,detail_json,created_at,prev_hash,hash) VALUES (?,?,?,?,?,?)",
                 (session_id, event_type, detail_json, created, prev, _hash(prev, session_id, event_type, detail_json, created)))


def events(conn: sqlite3.Connection, session_id: str) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM audit_events WHERE session_id=? ORDER BY seq", (session_id,)).fetchall()
    return [{"seq": r["seq"], "event_type": r["event_type"], "detail": json.loads(r["detail_json"]), "created_at": r["created_at"]} for r in rows]


def verify_chain(conn: sqlite3.Connection, session_id: str) -> bool:
    prev = GENESIS
    for r in conn.execute("SELECT * FROM audit_events WHERE session_id=? ORDER BY seq", (session_id,)).fetchall():
        if r["prev_hash"] != prev or r["hash"] != _hash(prev, session_id, r["event_type"], r["detail_json"], r["created_at"]):
            return False
        prev = r["hash"]
    return True
