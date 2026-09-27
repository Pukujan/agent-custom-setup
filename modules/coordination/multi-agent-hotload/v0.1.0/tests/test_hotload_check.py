"""Tests for multi-agent hotload_check."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = MODULE_ROOT / "scripts" / "hotload_check.py"


def _load_mod():
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("hotload_check", SCRIPT)
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_required_files_exist():
    mod = _load_mod()
    assert mod.check_required_files(MODULE_ROOT) == []


def test_example_validates_against_schema():
    mod = _load_mod()
    errors = mod.validate_assignment(
        MODULE_ROOT / "schema" / "assignment.schema.json",
        MODULE_ROOT / "examples" / "assignment.example.json",
    )
    assert errors == [], errors


def test_lease_ttl_rejects_short_window(tmp_path: Path):
    mod = _load_mod()
    good = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    good["boss_failover"]["lease_ttl_hours"] = 0.5  # ~30m — forbidden
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    errors = mod.validate_assignment(
        MODULE_ROOT / "schema" / "assignment.schema.json", path
    )
    assert any("lease_ttl_hours" in e for e in errors)


def test_watchdog_runner_must_be_agentless(tmp_path: Path):
    mod = _load_mod()
    good = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    good["watchdog"]["runner"] = "llm_agent"  # invalid
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    errors = mod.validate_assignment(
        MODULE_ROOT / "schema" / "assignment.schema.json", path
    )
    assert any("runner" in e for e in errors)


def test_cli_ok():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "hotload_check: OK" in proc.stdout


def test_watchdog_evaluate_paths():
    from importlib.util import module_from_spec, spec_from_file_location
    from datetime import datetime, timezone, timedelta

    wscript = MODULE_ROOT / "scripts" / "watchdog_check.py"
    spec = spec_from_file_location("watchdog_check", wscript)
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    now = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    assert (
        mod.evaluate(
            last_heartbeat=now - timedelta(minutes=5),
            last_github_activity=now,
            lease_ttl_hours=12,
            idle_window_minutes=45,
            now=now,
        )
        == "noop"
    )
    assert (
        mod.evaluate(
            last_heartbeat=now - timedelta(hours=13),
            last_github_activity=None,
            lease_ttl_hours=12,
            idle_window_minutes=45,
            now=now,
        )
        == "vacant"
    )
