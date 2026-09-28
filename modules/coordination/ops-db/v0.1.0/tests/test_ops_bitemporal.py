from __future__ import annotations
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
# Prefer this module's ops_db over jev-shared/scripts/ops_db if both are on path.
sys.path = [str(SCRIPTS)] + [x for x in sys.path if Path(x).resolve() != SCRIPTS.resolve()]
sys.modules.pop("ops_db", None)
from ops_db import (  # noqa: E402
    append_gate_event,
    append_claim_snapshot,
    as_of_gate_events,
    as_of_claim_snapshots,
    fifo_evict_partitioned,
    connect,
    PARTITION_POLICY,
)

def test_as_of_replay_recorded_at_prefix(tmp_path):
    db = tmp_path / "ops.sqlite"
    append_gate_event(gate_kind="research", decision="yes", reason_code="a",
                      occurred_at="2026-09-28T10:00:00Z", recorded_at="2026-09-28T10:00:01Z", db_path=db)
    append_gate_event(gate_kind="research", decision="no", reason_code="b",
                      occurred_at="2026-09-28T11:00:00Z", recorded_at="2026-09-28T11:00:01Z", db_path=db)
    append_gate_event(gate_kind="research", decision="yes", reason_code="future",
                      occurred_at="2026-09-28T13:00:00Z", recorded_at="2026-09-28T13:00:01Z", db_path=db)
    rows = as_of_gate_events(gate_kind="research", as_of="2026-09-28T12:00:00Z", db_path=db)
    assert rows and rows[0]["reason_code"] == "b"
    assert "future" not in {r["reason_code"] for r in rows}

def test_namespaces_and_claim(tmp_path):
    db = tmp_path / "ops.sqlite"
    append_claim_snapshot(issue_ref="#24", claim_text="need docs",
                          occurred_at="2026-09-28T09:00:00Z", recorded_at="2026-09-28T09:00:02Z", db_path=db)
    append_gate_event(gate_kind="ambiguity", decision="clear", reason_code="c",
                      occurred_at="2026-09-28T09:00:00Z", recorded_at="2026-09-28T09:00:03Z", db_path=db)
    claims = as_of_claim_snapshots(issue_ref="#24", as_of="2026-09-28T12:00:00Z", db_path=db)
    gates = as_of_gate_events(gate_kind="ambiguity", as_of="2026-09-28T12:00:00Z", db_path=db)
    assert claims and claims[0]["issue_ref"] == "#24"
    assert gates and gates[0]["gate_kind"] == "ambiguity"

def test_redacts_secrets(tmp_path):
    db = tmp_path / "ops.sqlite"
    append_gate_event(gate_kind="tool_pin", decision="deny", reason_code="x",
                      notes="api_key=sk-SECRETVALUE999", db_path=db)
    rows = as_of_gate_events(gate_kind="tool_pin", db_path=db)
    assert "SECRETVALUE" not in (rows[0]["notes_redacted"] or "")
    assert "REDACTED" in (rows[0]["notes_redacted"] or "")

def test_per_partition_fifo_spares_claims(tmp_path):
    """Tool spam eviction must NOT wipe claim SoT snaps (separate longer policy)."""
    db = tmp_path / "ops.sqlite"
    # old tool call + old claim, both aged out of short tool FIFO but claim still in 90d window
    conn = connect(db)
    conn.execute(
        """INSERT INTO transcript_tool_calls
           (uuid, session_id, tool_name, input_redacted, occurred_at, recorded_at)
           VALUES ('t1','s','Bash','x','2020-01-01T00:00:00Z','2020-01-01T00:00:00Z')"""
    )
    conn.execute(
        """INSERT INTO claim_snapshots
           (uuid, session_id, issue_ref, claim_text_redacted, meta_json, occurred_at, recorded_at)
           VALUES ('c1','s','#24','keep me','{}','2026-09-01T00:00:00Z','2026-09-01T00:00:00Z')"""
    )
    conn.commit()
    conn.close()
    deleted = fifo_evict_partitioned(db_path=db)
    assert deleted.get("transcript_tool_calls", 0) >= 1
    conn = connect(db)
    claims = conn.execute("select issue_ref from claim_snapshots").fetchall()
    tools = conn.execute("select uuid from transcript_tool_calls").fetchall()
    conn.close()
    assert claims and claims[0][0] == "#24"
    assert tools == []
    assert PARTITION_POLICY["claim_snapshots"]["max_age_days"] > PARTITION_POLICY["transcript_tool_calls"]["max_age_days"]
