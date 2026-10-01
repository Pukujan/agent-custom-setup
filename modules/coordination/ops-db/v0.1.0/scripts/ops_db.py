#!/usr/bin/env python3
"""ACS shared ops.sqlite — fossil-style append-only buffer, per-partition FIFO.

Temporal: occurred_at (when it happened) + recorded_at (when ACS wrote it).
As-of = filter recorded_at <= T, then replay prefix in recorded_at order
(not classic bi-temporal valid_time SQL unless a bench forces it).

Retention (RESEARCH-ALIGNED lock, ACS #25):
  - ONE shared SQLite, partitioned by stream
  - FIFO/size caps PER PARTITION (not one global FIFO)
  - tool_calls / transcript noise: short FIFO
  - gate_events: longer retention
  - claim/issue SoT snaps (+ pins): NOT evicted with tool spam
  - embeds: same FIFO family as parent stream; never on JEV hot path

Lasting proof ONLY in git + GitHub issues + benchmarks. This DB is a buffer.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from redact import redact  # noqa: E402

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS transcript_sessions (
  uuid TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  cwd TEXT,
  meta_json TEXT,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcript_messages (
  uuid TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  role TEXT,
  content_redacted TEXT,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcript_tool_calls (
  uuid TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  tool_name TEXT,
  input_redacted TEXT,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gate_events (
  uuid TEXT PRIMARY KEY,
  session_id TEXT,
  gate_kind TEXT NOT NULL,
  decision TEXT NOT NULL,
  tool_name TEXT,
  reason_code TEXT,
  judge TEXT,
  notes_redacted TEXT,
  payload_redacted TEXT,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_snapshots (
  uuid TEXT PRIMARY KEY,
  session_id TEXT,
  issue_ref TEXT,
  claim_text_redacted TEXT,
  meta_json TEXT,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pin_snapshots (
  uuid TEXT PRIMARY KEY,
  session_id TEXT,
  pin_text_redacted TEXT,
  meta_json TEXT,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS embed_vectors (
  uuid TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_uuid TEXT NOT NULL,
  session_id TEXT,
  parent_stream TEXT NOT NULL,
  backend TEXT NOT NULL,
  dim INTEGER NOT NULL,
  text_redacted TEXT,
  vector BLOB NOT NULL,
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gate_recorded ON gate_events(recorded_at);
CREATE INDEX IF NOT EXISTS idx_tool_recorded ON transcript_tool_calls(recorded_at);
CREATE INDEX IF NOT EXISTS idx_claim_recorded ON claim_snapshots(recorded_at);
CREATE INDEX IF NOT EXISTS idx_embed_recorded ON embed_vectors(parent_stream, recorded_at);
"""

# Per-partition retention (age days, max rows). Pins/claims NOT tied to tool spam.
PARTITION_POLICY = {
    "transcript_tool_calls": {"max_age_days": 3, "max_rows": 20000},
    "transcript_messages": {"max_age_days": 3, "max_rows": 30000},
    "transcript_sessions": {"max_age_days": 7, "max_rows": 5000},
    "gate_events": {"max_age_days": 30, "max_rows": 20000},
    "claim_snapshots": {"max_age_days": 90, "max_rows": 5000},  # SoT snaps; not tool-FIFO
    "pin_snapshots": {"max_age_days": 90, "max_rows": 5000},    # pins; not tool-FIFO
    "embed_vectors": {"max_age_days": 3, "max_rows": 30000},    # default; parent overrides below
}

# Embeds inherit parent stream family when parent_stream set
EMBED_PARENT_AGE = {
    "tool": 3,
    "transcript": 3,
    "gate": 30,
    "claim": 90,
    "pin": 90,
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_ops_db_path() -> Path:
    env = os.environ.get("ACS_OPS_DB", "").strip()
    if env:
        return Path(env)
    return Path.home() / ".acs" / "ops.sqlite"



def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _cols(conn: sqlite3.Connection, table: str) -> set:
    if not _table_exists(conn, table):
        return set()
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _migrate_legacy(conn: sqlite3.Connection) -> None:
    """Upgrade older shapes: valid_time→occurred_at; embed parent_stream; pin_snapshots."""
    # embed_vectors: rebuild if missing parent_stream
    if _table_exists(conn, "embed_vectors"):
        cols = _cols(conn, "embed_vectors")
        if "parent_stream" not in cols or "occurred_at" not in cols:
            conn.execute("DROP TABLE IF EXISTS embed_vectors")

    # tables that may still have valid_time instead of occurred_at
    for table in (
        "gate_events",
        "claim_snapshots",
        "transcript_sessions",
        "transcript_messages",
        "transcript_tool_calls",
    ):
        if not _table_exists(conn, table):
            continue
        cols = _cols(conn, table)
        if "occurred_at" not in cols and "valid_time" in cols:
            conn.execute(f"ALTER TABLE {table} RENAME COLUMN valid_time TO occurred_at")
        elif "occurred_at" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN occurred_at TEXT")
            if "recorded_at" in cols:
                conn.execute(
                    f"UPDATE {table} SET occurred_at = recorded_at WHERE occurred_at IS NULL OR occurred_at = ''"
                )


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(path) if path else default_ops_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    _migrate_legacy(conn)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _eid(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]


def append_gate_event(
    *,
    gate_kind: str,
    decision: str,
    reason_code: str,
    tool_name: str = "",
    judge: str = "mock",
    notes: str = "",
    session_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    occurred_at: Optional[str] = None,
    recorded_at: Optional[str] = None,
    valid_time: Optional[str] = None,  # back-compat alias → occurred_at
    db_path: Optional[Path] = None,
) -> str:
    ot = occurred_at or valid_time or _now()
    rt = recorded_at or _now()
    notes_r = redact(notes or "")
    payload_r = redact(json.dumps(payload or {}, ensure_ascii=False))
    uuid = _eid(gate_kind, ot, rt, decision, reason_code, tool_name, notes_r[:80])
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO gate_events
               (uuid, session_id, gate_kind, decision, tool_name, reason_code, judge,
                notes_redacted, payload_redacted, occurred_at, recorded_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (uuid, session_id, gate_kind, decision, redact(tool_name or ""), reason_code,
             judge, notes_r, payload_r, ot, rt),
        )
        conn.commit()
    finally:
        conn.close()
    return uuid


def append_claim_snapshot(
    *,
    issue_ref: str,
    claim_text: str,
    session_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    occurred_at: Optional[str] = None,
    recorded_at: Optional[str] = None,
    valid_time: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> str:
    ot = occurred_at or valid_time or _now()
    rt = recorded_at or _now()
    claim_r = redact(claim_text or "")
    uuid = _eid("claim", ot, rt, issue_ref, claim_r[:120])
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO claim_snapshots
               (uuid, session_id, issue_ref, claim_text_redacted, meta_json, occurred_at, recorded_at)
               VALUES (?,?,?,?,?,?,?)""",
            (uuid, session_id, issue_ref, claim_r, json.dumps(meta or {}), ot, rt),
        )
        conn.commit()
    finally:
        conn.close()
    return uuid


append_issue_snapshot = append_claim_snapshot


def append_pin_snapshot(
    *,
    pin_text: str,
    session_id: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    occurred_at: Optional[str] = None,
    recorded_at: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> str:
    ot = occurred_at or _now()
    rt = recorded_at or _now()
    pin_r = redact(pin_text or "")
    uuid = _eid("pin", ot, rt, pin_r[:120])
    conn = connect(db_path)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO pin_snapshots
               (uuid, session_id, pin_text_redacted, meta_json, occurred_at, recorded_at)
               VALUES (?,?,?,?,?,?)""",
            (uuid, session_id, pin_r, json.dumps(meta or {}), ot, rt),
        )
        conn.commit()
    finally:
        conn.close()
    return uuid


def as_of_replay(
    table: str,
    *,
    as_of: Optional[str] = None,
    where_sql: str = "",
    where_args: tuple = (),
    db_path: Optional[Path] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Fossil as-of: recorded_at <= as_of, replay prefix ordered by recorded_at ASC."""
    as_of = as_of or _now()
    allowed = {
        "gate_events", "claim_snapshots", "pin_snapshots",
        "transcript_tool_calls", "transcript_messages", "transcript_sessions", "embed_vectors",
    }
    if table not in allowed:
        raise ValueError(f"unknown table {table}")
    conn = connect(db_path)
    try:
        sql = f"SELECT * FROM {table} WHERE recorded_at <= ?"
        args: list = [as_of]
        if where_sql:
            sql += f" AND ({where_sql})"
            args.extend(where_args)
        sql += " ORDER BY recorded_at ASC LIMIT ?"
        args.append(limit)
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def as_of_gate_events(
    *,
    gate_kind: Optional[str] = None,
    as_of: Optional[str] = None,
    db_path: Optional[Path] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Replay gate_events prefix as-of recorded_at (newest-last)."""
    where = "gate_kind=?" if gate_kind else ""
    args = (gate_kind,) if gate_kind else ()
    rows = as_of_replay("gate_events", as_of=as_of, where_sql=where, where_args=args,
                        db_path=db_path, limit=limit)
    # callers often want most-recent-backward view: reverse for convenience
    return list(reversed(rows))


def as_of_claim_snapshots(
    *,
    issue_ref: Optional[str] = None,
    as_of: Optional[str] = None,
    db_path: Optional[Path] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    where = "issue_ref=?" if issue_ref else ""
    args = (issue_ref,) if issue_ref else ()
    rows = as_of_replay("claim_snapshots", as_of=as_of, where_sql=where, where_args=args,
                        db_path=db_path, limit=limit)
    return list(reversed(rows))


def fifo_evict_partitioned(
    *,
    db_path: Optional[Path] = None,
    policy: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, int]:
    """Per-partition FIFO eviction. Pins/claims use their own long caps — not tool spam FIFO."""
    policy = policy or PARTITION_POLICY
    deleted: Dict[str, int] = {}
    conn = connect(db_path)
    now = datetime.now(timezone.utc)
    try:
        for table, cfg in policy.items():
            if table == "embed_vectors":
                # evict embeds by parent_stream family
                n = 0
                for parent, age in EMBED_PARENT_AGE.items():
                    cutoff = (now - timedelta(days=age)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    cur = conn.execute(
                        "DELETE FROM embed_vectors WHERE parent_stream=? AND recorded_at < ?",
                        (parent, cutoff),
                    )
                    n += cur.rowcount or 0
                # size cap overall
                max_rows = cfg["max_rows"]
                count = conn.execute("SELECT COUNT(*) FROM embed_vectors").fetchone()[0]
                if count > max_rows:
                    overflow = count - max_rows
                    cur2 = conn.execute(
                        """DELETE FROM embed_vectors WHERE uuid IN (
                             SELECT uuid FROM embed_vectors ORDER BY recorded_at ASC LIMIT ?
                           )""",
                        (overflow,),
                    )
                    n += cur2.rowcount or 0
                deleted[table] = n
                continue

            max_age = cfg["max_age_days"]
            max_rows = cfg["max_rows"]
            cutoff = (now - timedelta(days=max_age)).strftime("%Y-%m-%dT%H:%M:%SZ")
            cur = conn.execute(f"DELETE FROM {table} WHERE recorded_at < ?", (cutoff,))
            n = cur.rowcount or 0
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if count > max_rows:
                overflow = count - max_rows
                cur2 = conn.execute(
                    f"""DELETE FROM {table} WHERE uuid IN (
                         SELECT uuid FROM {table} ORDER BY recorded_at ASC LIMIT ?
                       )""",
                    (overflow,),
                )
                n += cur2.rowcount or 0
            deleted[table] = int(n)
        conn.commit()
    finally:
        conn.close()
    return deleted


# back-compat name
fifo_evict = fifo_evict_partitioned
