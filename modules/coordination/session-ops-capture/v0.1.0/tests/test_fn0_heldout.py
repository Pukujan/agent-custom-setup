"""Held-out FN=0: planted gate-relevant tools must not be missed by mock classify."""

from __future__ import annotations

import json
from pathlib import Path

from session_ops_capture.db import SessionOpsDB
from session_ops_capture.ingest import ingest_once

ROOT = Path(__file__).parent / "fixtures" / "held_out_fn0"


def test_heldout_fn0_no_missed_gate_relevant(tmp_path: Path) -> None:
    expect = json.loads((ROOT / "expect.json").read_text(encoding="utf-8"))
    db_path = tmp_path / "fn0.sqlite"
    ingest_once(
        jsonl=ROOT / "plants.jsonl",
        db_path=db_path,
        export_otlp=False,
        force_mock_classify=True,
    )
    with SessionOpsDB(db_path) as db:
        by_uuid = {r["uuid"]: r for r in db.fetch_classifications()}
    misses = []
    for tool_id, exp in expect.items():
        row = by_uuid.get(f"tool:{tool_id}")
        if row is None:
            misses.append((tool_id, "missing_classification"))
            continue
        if exp.get("gate_relevant") and not row["gate_relevant"]:
            misses.append((tool_id, "FN_gate_relevant"))
        if exp.get("risk_class") and row["risk_class"] != exp["risk_class"]:
            # risk mismatch counted as soft miss for FN package
            misses.append((tool_id, f"risk_got_{row['risk_class']}"))
    assert misses == [], f"FN!=0 misses={misses}"
