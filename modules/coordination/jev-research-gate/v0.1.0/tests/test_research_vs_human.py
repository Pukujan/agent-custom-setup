"""Research gate vs human/#14 checklist fallback contract."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "research_gate.py"
FIX = ROOT / "fixtures"

def _run(fixture: Path, judge="mock"):
    proc = subprocess.run([sys.executable, str(GATE), "--fixture", str(fixture), "--judge", judge, "--json"], capture_output=True, text=True)
    return json.loads(proc.stdout), proc.returncode

def test_needs_research_yes():
    data, rc = _run(FIX / "needs_research.json")
    assert data["decision"] == "yes"
    assert data["fallback"].startswith("#14")

def test_no_research():
    data, rc = _run(FIX / "no_research.json")
    assert data["decision"] == "no"

def test_insufficient_points_to_checklist():
    data, rc = _run(FIX / "insufficient_claim.json")
    assert data["decision"] == "insufficient"
    assert "#14" in data["fallback"]

def test_openrouter_without_live_flag_insufficient_not_human(monkeypatch):
    monkeypatch.delenv("ACS_JEV_LIVE", raising=False)
    import os
    env = {k: v for k, v in os.environ.items() if k != "ACS_JEV_LIVE"}
    proc = __import__("subprocess").run(
        [__import__("sys").executable, str(GATE), "--fixture", str(FIX / "needs_research.json"),
         "--judge", "openrouter", "--json"],
        capture_output=True, text=True, env=env,
    )
    data = __import__("json").loads(proc.stdout)
    # Without ACS_JEV_LIVE, fail toward checklist — not a human boss ask
    assert data["decision"] == "insufficient"
    assert "checklist" in data["reason_code"] or "checklist" in data["fallback"]
