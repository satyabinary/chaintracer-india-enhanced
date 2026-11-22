"""
Plain sqlite3 data layer — no ORM, kept deliberately simple per the brief.

One table, `cases`, holds everything: the case metadata the officer enters,
plus the full trace/risk output stored as JSON columns. For a tool at this
scale that's simpler and more transparent than normalizing transactions
into their own tables, and it means the whole case record can be handed
to the PDF generator or the frontend as a single JSON blob.
"""
import sqlite3
import json
import threading
from contextlib import contextmanager

from app.config import DB_PATH

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number TEXT UNIQUE NOT NULL,
    victim_name TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    amount_usdt REAL NOT NULL,
    notes TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'TRACING',      -- TRACING | TRACED | UNVERIFIED | FAILED | RATE_LIMITED
    match_status TEXT,                            -- EXCHANGE_MATCH | SWEEPER_MATCH | IN_TRANSIT | MIXER_FLAGGED | AMOUNT_NOT_VERIFIED | TRACE_FAILED | RATE_LIMITED | TRACE_INCOMPLETE_RATE_LIMITED
    matched_exchange TEXT,
    matched_exchange_verified INTEGER,             -- NULL = no match, 0 = sample data, 1 = Tronscan-labeled (verified)
    matched_exchange_note TEXT,                     -- human-readable "Verified match — X" / "Sample match — X" label
    matched_wallet TEXT,
    risk_score REAL,
    priority TEXT,                                 -- HIGH | MEDIUM | LOW
    error_message TEXT,
    trace_result_json TEXT,                        -- raw trace_engine output
    risk_breakdown_json TEXT,                       -- risk_engine output
    graph_json TEXT,                                -- cytoscape nodes/edges
    evidence_json TEXT,                             -- evidence table rows
    is_seed INTEGER NOT NULL DEFAULT 0,
    alert_sent INTEGER NOT NULL DEFAULT 0,          -- simulated "alert sent to exchange" flag only
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    """One connection per thread (FastAPI's threadpool executor uses several)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _local.conn = conn
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_add_missing_columns(conn)


def _migrate_add_missing_columns(conn):
    """
    Lightweight, additive migration. `CREATE TABLE IF NOT EXISTS` above only
    creates the table on a brand-new database — if a chaintracer.db from
    before a column was added (e.g. matched_exchange_verified,
    matched_exchange_note) already exists on disk, it's left untouched and
    would otherwise crash the next INSERT with a column-count mismatch. This
    adds any missing column instead, so upgrading in place just works.
    """
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(cases)").fetchall()}
    additive_columns = {
        "matched_exchange_verified": "INTEGER",
        "matched_exchange_note": "TEXT",
        # Owner of the case. NULL = seed/demo case, visible to nobody who
        # logs in (see routers/cases.py). Existing rows keep NULL on upgrade.
        "owner_user_id": "INTEGER",
    }
    for col, col_type in additive_columns.items():
        if col not in existing_columns:
            conn.execute(f"ALTER TABLE cases ADD COLUMN {col} {col_type}")
    conn.commit()


@contextmanager
def get_cursor(commit: bool = False):
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    finally:
        cur.close()


def row_to_case_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for json_field in ("trace_result_json", "risk_breakdown_json", "graph_json", "evidence_json"):
        raw = d.pop(json_field, None)
        key = json_field.replace("_json", "")
        d[key] = json.loads(raw) if raw else None
    d["is_seed"] = bool(d.get("is_seed"))
    d["alert_sent"] = bool(d.get("alert_sent"))
    if d.get("matched_exchange_verified") is not None:
        d["matched_exchange_verified"] = bool(d["matched_exchange_verified"])
    return d