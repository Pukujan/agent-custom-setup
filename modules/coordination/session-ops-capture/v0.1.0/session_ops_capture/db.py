"""Idempotent local SQLite buffer (uuid-keyed)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  cwd TEXT,
  started_at TEXT,
  ended_at TEXT,
  meta_json TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  uuid TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  parent_uuid TEXT,
  role TEXT,
  type TEXT,
  timestamp TEXT,
  content_redacted TEXT,
  interaction_index INTEGER,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
  uuid TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  message_uuid TEXT,
  tool_name TEXT,
  tool_use_id TEXT,
  input_redacted TEXT,
  result_redacted TEXT,
  timestamp TEXT,
  interaction_index INTEGER,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tool_calls_tool_use_id
  ON tool_calls(tool_use_id) WHERE tool_use_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS gate_events (
  uuid TEXT PRIMARY KEY,
  session_id TEXT,
  ts TEXT,
  decision TEXT,
  tool_name TEXT,
  reason_code TEXT,
  judge TEXT,
  notes_redacted TEXT,
  payload_redacted TEXT
);

CREATE TABLE IF NOT EXISTS classifications (
  uuid TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  session_id TEXT,
  risk_class TEXT,
  research_needed INTEGER,
  gate_relevant INTEGER,
  labels_json TEXT,
  classify_judge TEXT,
  classify_rationale TEXT,
  classified_at TEXT
);

CREATE TABLE IF NOT EXISTS embeddings (
  uuid TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  session_id TEXT,
  backend TEXT NOT NULL,
  dim INTEGER NOT NULL,
  text_redacted TEXT,
  vector BLOB NOT NULL,
  embedded_at TEXT
);

CREATE TABLE IF NOT EXISTS ingest_meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


class SessionOpsDB:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "SessionOpsDB":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def upsert_session(
        self,
        session_id: str,
        cwd: Optional[str] = None,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        cur = self.conn.execute(
            "SELECT session_id, cwd, started_at, ended_at, meta_json FROM sessions WHERE session_id=?",
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO sessions(session_id, cwd, started_at, ended_at, meta_json) VALUES (?,?,?,?,?)",
                (
                    session_id,
                    cwd,
                    started_at,
                    ended_at,
                    json.dumps(meta or {}, ensure_ascii=False, sort_keys=True),
                ),
            )
            return
        new_cwd = cwd if cwd is not None else row["cwd"]
        new_started = row["started_at"] or started_at
        if started_at and row["started_at"] and started_at < row["started_at"]:
            new_started = started_at
        new_ended = row["ended_at"]
        if ended_at:
            if not row["ended_at"] or ended_at > row["ended_at"]:
                new_ended = ended_at
        meta_json = row["meta_json"]
        if meta:
            try:
                existing = json.loads(meta_json or "{}")
            except json.JSONDecodeError:
                existing = {}
            existing.update(meta)
            meta_json = json.dumps(existing, ensure_ascii=False, sort_keys=True)
        self.conn.execute(
            "UPDATE sessions SET cwd=?, started_at=?, ended_at=?, meta_json=? WHERE session_id=?",
            (new_cwd, new_started, new_ended, meta_json, session_id),
        )

    def upsert_message(self, row: Dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO messages(uuid, session_id, parent_uuid, role, type, timestamp,
                                 content_redacted, interaction_index)
            VALUES (:uuid, :session_id, :parent_uuid, :role, :type, :timestamp,
                    :content_redacted, :interaction_index)
            ON CONFLICT(uuid) DO UPDATE SET
              session_id=excluded.session_id,
              parent_uuid=excluded.parent_uuid,
              role=excluded.role,
              type=excluded.type,
              timestamp=excluded.timestamp,
              content_redacted=excluded.content_redacted,
              interaction_index=excluded.interaction_index
            """,
            row,
        )

    def upsert_tool_call(self, row: Dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO tool_calls(uuid, session_id, message_uuid, tool_name, tool_use_id,
                                   input_redacted, result_redacted, timestamp, interaction_index)
            VALUES (:uuid, :session_id, :message_uuid, :tool_name, :tool_use_id,
                    :input_redacted, :result_redacted, :timestamp, :interaction_index)
            ON CONFLICT(uuid) DO UPDATE SET
              session_id=excluded.session_id,
              message_uuid=COALESCE(excluded.message_uuid, tool_calls.message_uuid),
              tool_name=COALESCE(excluded.tool_name, tool_calls.tool_name),
              tool_use_id=COALESCE(excluded.tool_use_id, tool_calls.tool_use_id),
              input_redacted=CASE
                WHEN excluded.input_redacted IS NOT NULL AND excluded.input_redacted != ''
                THEN excluded.input_redacted ELSE tool_calls.input_redacted END,
              result_redacted=CASE
                WHEN excluded.result_redacted IS NOT NULL AND excluded.result_redacted != ''
                THEN excluded.result_redacted ELSE tool_calls.result_redacted END,
              timestamp=COALESCE(excluded.timestamp, tool_calls.timestamp),
              interaction_index=COALESCE(excluded.interaction_index, tool_calls.interaction_index)
            """,
            row,
        )

    def upsert_gate_event(self, row: Dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO gate_events(uuid, session_id, ts, decision, tool_name, reason_code,
                                    judge, notes_redacted, payload_redacted)
            VALUES (:uuid, :session_id, :ts, :decision, :tool_name, :reason_code,
                    :judge, :notes_redacted, :payload_redacted)
            ON CONFLICT(uuid) DO UPDATE SET
              session_id=excluded.session_id,
              ts=excluded.ts,
              decision=excluded.decision,
              tool_name=excluded.tool_name,
              reason_code=excluded.reason_code,
              judge=excluded.judge,
              notes_redacted=excluded.notes_redacted,
              payload_redacted=excluded.payload_redacted
            """,
            row,
        )

    def commit(self) -> None:
        self.conn.commit()

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for table in (
            "sessions",
            "messages",
            "tool_calls",
            "gate_events",
            "classifications",
            "embeddings",
        ):
            out[table] = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return out

    def fingerprint(self) -> str:
        """Stable content fingerprint for metamorphic / idempotency checks."""
        h = hashlib.sha256()
        for table, order in (
            ("sessions", "session_id"),
            ("messages", "uuid"),
            ("tool_calls", "uuid"),
            ("gate_events", "uuid"),
            ("classifications", "uuid"),
            ("embeddings", "uuid"),
        ):
            cols = [r[1] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            col_list = ", ".join(cols)
            for row in self.conn.execute(f"SELECT {col_list} FROM {table} ORDER BY {order}"):
                payload = json.dumps(list(row), ensure_ascii=False, default=str)
                h.update(table.encode())
                h.update(b"\0")
                h.update(payload.encode())
                h.update(b"\n")
        return h.hexdigest()


    def upsert_classification(self, row: Dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO classifications(uuid, entity_type, session_id, risk_class,
                                        research_needed, gate_relevant, labels_json,
                                        classify_judge, classify_rationale, classified_at)
            VALUES (:uuid, :entity_type, :session_id, :risk_class,
                    :research_needed, :gate_relevant, :labels_json,
                    :classify_judge, :classify_rationale, :classified_at)
            ON CONFLICT(uuid) DO UPDATE SET
              entity_type=excluded.entity_type,
              session_id=excluded.session_id,
              risk_class=excluded.risk_class,
              research_needed=excluded.research_needed,
              gate_relevant=excluded.gate_relevant,
              labels_json=excluded.labels_json,
              classify_judge=excluded.classify_judge,
              classify_rationale=excluded.classify_rationale,
              classified_at=excluded.classified_at
            """,
            row,
        )

    def upsert_embedding(self, row: Dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO embeddings(uuid, entity_type, session_id, backend, dim,
                                   text_redacted, vector, embedded_at)
            VALUES (:uuid, :entity_type, :session_id, :backend, :dim,
                    :text_redacted, :vector, :embedded_at)
            ON CONFLICT(uuid) DO UPDATE SET
              entity_type=excluded.entity_type,
              session_id=excluded.session_id,
              backend=excluded.backend,
              dim=excluded.dim,
              text_redacted=excluded.text_redacted,
              vector=excluded.vector,
              embedded_at=excluded.embedded_at
            """,
            row,
        )

    def fetch_classifications(self) -> List[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM classifications ORDER BY uuid"))

    def fetch_embeddings(self) -> List[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM embeddings ORDER BY uuid"))

    def fetch_tool_calls(self) -> List[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM tool_calls ORDER BY interaction_index, timestamp, uuid"
            )
        )

    def fetch_gate_events(self) -> List[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM gate_events ORDER BY ts, uuid"))

    def fetch_messages(self) -> List[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM messages ORDER BY interaction_index, timestamp, uuid"
            )
        )

    def fetch_sessions(self) -> List[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM sessions ORDER BY session_id"))

    def all_text_blobs(self) -> Iterable[str]:
        for table, cols in (
            ("sessions", ("cwd", "meta_json")),
            ("messages", ("content_redacted",)),
            ("tool_calls", ("input_redacted", "result_redacted", "tool_name")),
            ("gate_events", ("tool_name", "notes_redacted", "payload_redacted")),
        ):
            col_list = ", ".join(cols)
            for row in self.conn.execute(f"SELECT {col_list} FROM {table}"):
                for v in row:
                    if isinstance(v, str):
                        yield v
