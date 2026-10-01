"""Property / idempotency tests for SQLite buffer."""

from __future__ import annotations

from pathlib import Path

import pytest

from session_ops_capture.db import SessionOpsDB
from session_ops_capture.ingest import ingest_once


FIXTURES = Path(__file__).parent / "fixtures"


def test_idempotent_double_ingest(tmp_path: Path) -> None:
    db_path = tmp_path / "ops.sqlite"
    jsonl = FIXTURES / "sample_session.jsonl"
    r1 = ingest_once(jsonl=jsonl, db_path=db_path, export_otlp=False)
    r2 = ingest_once(jsonl=jsonl, db_path=db_path, export_otlp=False)
    assert r1["counts"] == r2["counts"]
    assert r1["fingerprint"] == r2["fingerprint"]
    assert r1["counts"]["tool_calls"] >= 3
    assert r1["counts"]["sessions"] == 1


def test_gate_ingest_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "ops.sqlite"
    gate = FIXTURES / "sample_gate.jsonl"
    r1 = ingest_once(jsonl=None, db_path=db_path, gate_jsonl=gate, export_otlp=False)
    r2 = ingest_once(jsonl=None, db_path=db_path, gate_jsonl=gate, export_otlp=False)
    assert r1["counts"]["gate_events"] == 3
    assert r1["fingerprint"] == r2["fingerprint"]


def test_upsert_message_uuid_stable(tmp_path: Path) -> None:
    db = SessionOpsDB(tmp_path / "x.sqlite")
    row = {
        "uuid": "m1",
        "session_id": "s1",
        "parent_uuid": None,
        "role": "user",
        "type": "user",
        "timestamp": "t1",
        "content_redacted": "[]",
        "interaction_index": 1,
    }
    db.upsert_session("s1", cwd="/tmp")
    db.upsert_message(row)
    row2 = dict(row)
    row2["content_redacted"] = '[{"type":"text","text":"hi"}]'
    db.upsert_message(row2)
    db.commit()
    assert db.counts()["messages"] == 1
    got = db.fetch_messages()[0]
    assert "hi" in got["content_redacted"]
    db.close()
