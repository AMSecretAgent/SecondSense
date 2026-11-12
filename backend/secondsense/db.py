"""SQLite access. Explicit transactions (BEGIN IMMEDIATE) so state transitions are atomic."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  owner_hash TEXT NOT NULL,
  item_id TEXT NOT NULL,
  item_label TEXT NOT NULL,
  amount_value TEXT NOT NULL,
  currency TEXT NOT NULL,
  risk_score INTEGER NOT NULL,
  risk_level TEXT NOT NULL,
  signals_json TEXT NOT NULL,          -- signal names + points only; never message text or evidence
  context_chars INTEGER NOT NULL,      -- length only; the raw message is never persisted
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  ack_at TEXT, ack_digest TEXT, ack_risk_score INTEGER,
  order_id TEXT, order_created_at TEXT,
  capture_started_at TEXT, capture_id TEXT, captured_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_owner ON sessions(owner_hash, created_at DESC);
CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY,
  token_hash TEXT UNIQUE NOT NULL,     -- SHA-256 of the bearer token; token itself is never stored
  session_id TEXT NOT NULL REFERENCES sessions(id),
  consent_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  verdict TEXT, verdict_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_reviews_session ON reviews(session_id);
CREATE TABLE IF NOT EXISTS audit_events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  detail_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_events(session_id, seq);
"""


def init_db(path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(path: Path) -> Iterator[sqlite3.Connection]:
    with connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")
