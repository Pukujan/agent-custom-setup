"""Fish fixture tests: FN=0 on block for mock judge."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = MODULE_ROOT / "scripts"
FIXTURES = MODULE_ROOT / "fixtures" / "fish_hosted_vs_selfhost"
GATE = SCRIPTS / "gate.py"


def _run_gate(fixture: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(GATE), "--fixture", str(fixture), "--judge", "mock", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.stdout.strip(), f"empty stdout rc={proc.returncode} stderr={proc.stderr}"
    return json.loads(proc.stdout)


def _load_fixtures():
    return sorted(FIXTURES.glob("*.json"))


def test_fixtures_exist():
    files = _load_fixtures()
    assert len(files) >= 2
    golds = {json.loads(p.read_text(encoding="utf-8"))["gold_decision"] for p in files}
    assert "deny" in golds
    assert "allow" in golds


def test_fn_zero_on_block():
    """Every gold=block/deny fixture must get deny (false-negative = 0 on block)."""
    false_negatives = []
    for path in _load_fixtures():
        fx = json.loads(path.read_text(encoding="utf-8"))
        gold = fx.get("gold_decision")
        if gold not in ("deny", "block"):
            continue
        result = _run_gate(path)
        if result["decision"] != "deny":
            false_negatives.append(
                {
                    "id": fx.get("id"),
                    "got": result["decision"],
                    "reason": result.get("reason_code"),
                }
            )
    assert false_negatives == [], f"FN on block: {false_negatives}"


def test_allow_fixtures_not_denied():
    """Allow fixtures should not be incorrectly denied by mock judge."""
    bad = []
    for path in _load_fixtures():
        fx = json.loads(path.read_text(encoding="utf-8"))
        if fx.get("gold_decision") != "allow":
            continue
        result = _run_gate(path)
        if result["decision"] == "deny":
            bad.append({"id": fx.get("id"), "got": result})
    assert bad == [], f"allow fixtures incorrectly denied: {bad}"


def test_inferhub_fails_closed_escalate():
    proc = subprocess.run(
        [
            sys.executable,
            str(GATE),
            "--fixture",
            str(FIXTURES / "allow_hosted_api_tool.json"),
            "--judge",
            "inferhub",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "JEV_INFERHUB_GATE_ENABLED": ""},
    )
    data = json.loads(proc.stdout)
    assert data["decision"] == "escalate"
    assert proc.returncode == 3
