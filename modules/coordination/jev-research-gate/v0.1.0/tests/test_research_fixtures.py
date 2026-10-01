from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "research_gate.py"
FIX = ROOT / "fixtures"
DB = ROOT / "tests" / "_tmp_ops.sqlite"

def run_fx(name: str) -> dict:
    p = subprocess.run([sys.executable, str(GATE), "--fixture", str(FIX / name), "--judge", "mock", "--json", "--ops-db", str(DB)],
                       capture_output=True, text=True, check=False)
    assert p.stdout.strip(), p.stderr
    return json.loads(p.stdout)

def test_gold_fixtures():
    for name in ("needs_research.json", "no_research.json", "insufficient_claim.json"):
        fx = json.loads((FIX / name).read_text(encoding="utf-8"))
        got = run_fx(name)
        assert got["decision"] == fx["gold_decision"], (name, got)

def test_metamorphic_whitespace():
    fx = json.loads((FIX / "needs_research.json").read_text(encoding="utf-8"))
    a = subprocess.run([sys.executable, str(GATE), "--claim", fx["claim_text"], "--judge", "mock", "--json"], capture_output=True, text=True)
    b = subprocess.run([sys.executable, str(GATE), "--claim", " ".join(fx["claim_text"].split()), "--judge", "mock", "--json"], capture_output=True, text=True)
    assert json.loads(a.stdout)["decision"] == json.loads(b.stdout)["decision"]

def test_ops_db_both_tables(tmp_path):
    import sqlite3
    db = tmp_path / "ops.sqlite"
    p = subprocess.run([sys.executable, str(GATE), "--fixture", str(FIX / "needs_research.json"), "--judge", "mock", "--json", "--ops-db", str(db)],
                   capture_output=True, text=True, check=False)
    assert p.stdout.strip(), p.stderr
    assert json.loads(p.stdout)["decision"] == "yes"
    conn = sqlite3.connect(db)
    g = conn.execute("select gate_kind, decision from gate_events").fetchall()
    s = conn.execute("select issue_ref from claim_snapshots").fetchall()
    assert g and g[0][0] == "research"
    assert s

def test_claude_and_kilo_smoke():
    hook = ROOT / "hooks" / "claude_claim_snapshot.py"
    p = subprocess.run([sys.executable, str(hook)], input=json.dumps({"claim_text": "unit test in-repo fixture", "known_docs": ["a.md"]}),
                       capture_output=True, text=True)
    assert json.loads(p.stdout)["decision"] == "no"
    stub = ROOT / "adapters" / "kilo_stub.py"
    p2 = subprocess.run([sys.executable, str(stub), "--snapshot", str(FIX / "needs_research.json"), "--json"], capture_output=True, text=True)
    assert json.loads(p2.stdout)["wiring"] == "stub"

