from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "claude_pretooluse.py"
STUB = ROOT / "adapters" / "kilo_stub.py"
FIX = ROOT / "fixtures" / "fish_hosted_vs_selfhost"

def test_claude_pretooluse_deny_selfhost():
    fx = json.loads((FIX / "block_selfhost_despite_hosted_brief.json").read_text(encoding="utf-8"))
    payload = {
        "tool_name": fx["proposed_tool"]["name"],
        "tool_input": {"command": fx["proposed_tool"]["args_summary"]},
        "brief": fx["brief"],
        "corrections": fx["corrections"],
    }
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True)
    data = json.loads(p.stdout)
    assert data.get("gate_decision") == "deny" or data["hookSpecificOutput"]["permissionDecision"] == "deny"

def test_kilo_stub_allow():
    p = subprocess.run([sys.executable, str(STUB), "--fixture", str(FIX / "allow_hosted_api_tool.json"), "--json"],
                       capture_output=True, text=True)
    data = json.loads(p.stdout)
    assert data["wiring"] == "stub"
    assert data["decision"] == "allow"

def test_ops_db_tool_pin(tmp_path):
    gate = ROOT / "scripts" / "gate.py"
    db = tmp_path / "ops.sqlite"
    subprocess.run([sys.executable, str(gate), "--fixture", str(FIX / "block_selfhost_despite_hosted_brief.json"),
                    "--judge", "mock", "--json", "--ops-db", str(db)], capture_output=True, text=True, check=False)
    import sqlite3
    conn = sqlite3.connect(db)
    rows = conn.execute("select gate_kind, decision from gate_events").fetchall()
    assert rows and rows[0][0] == "tool_pin" and rows[0][1] == "deny"
