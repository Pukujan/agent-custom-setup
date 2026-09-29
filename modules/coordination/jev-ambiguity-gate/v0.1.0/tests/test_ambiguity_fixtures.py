from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "ambiguity_gate.py"
FIX = ROOT / "fixtures"

def run_fx(name: str) -> dict:
    p = subprocess.run([sys.executable, str(GATE), "--fixture", str(FIX / name), "--judge", "mock", "--json",
                        "--ops-db", str(ROOT / "tests" / "_tmp_ops.sqlite")],
                       capture_output=True, text=True, check=False)
    assert p.stdout.strip(), p.stderr
    return json.loads(p.stdout)

def test_fn_zero_on_ambiguous_and_insufficient():
    bad = []
    for name in ("ambiguous_prompt.json", "insufficient_resume.json"):
        fx = json.loads((FIX / name).read_text(encoding="utf-8"))
        got = run_fx(name)
        if got["decision"] != fx["gold_decision"]:
            bad.append((fx["id"], got["decision"]))
    assert bad == [], bad

def test_clear_fixture():
    got = run_fx("clear_prompt.json")
    assert got["decision"] == "clear"

def test_metamorphic_reorder_whitespace():
    fx = json.loads((FIX / "ambiguous_prompt.json").read_text(encoding="utf-8"))
    a = subprocess.run([sys.executable, str(GATE), "--prompt", fx["prompt"], "--resume", fx["resume_context"], "--judge", "mock", "--json"],
                       capture_output=True, text=True, check=False)
    b_prompt = "  ".join(fx["prompt"].split())
    b = subprocess.run([sys.executable, str(GATE), "--prompt", b_prompt, "--resume", fx["resume_context"], "--judge", "mock", "--json"],
                       capture_output=True, text=True, check=False)
    assert json.loads(a.stdout)["decision"] == json.loads(b.stdout)["decision"]

def test_claude_hook_smoke():
    hook = ROOT / "hooks" / "claude_user_prompt.py"
    payload = json.dumps({"prompt": "whatever somehow", "hook_event_name": "UserPromptSubmit"})
    p = subprocess.run([sys.executable, str(hook)], input=payload, capture_output=True, text=True, check=False)
    data = json.loads(p.stdout)
    assert "hookSpecificOutput" in data

def test_kilo_stub_smoke():
    stub = ROOT / "adapters" / "kilo_stub.py"
    snap = FIX / "clear_prompt.json"
    p = subprocess.run([sys.executable, str(stub), "--snapshot", str(snap), "--json"], capture_output=True, text=True, check=False)
    data = json.loads(p.stdout)
    assert data["wiring"] == "stub"
    assert data["decision"] == "clear"
