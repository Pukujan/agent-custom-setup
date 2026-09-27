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


def test_lease_ttl_accepts_default_30(tmp_path: Path):
    mod = _load_mod()
    good = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    assert good["boss_failover"]["lease_ttl_minutes"] == 30
    path = tmp_path / "ok.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    errors = mod.validate_assignment(
        MODULE_ROOT / "schema" / "assignment.schema.json", path
    )
    assert errors == [], errors


def test_lease_ttl_rejects_too_short_and_legacy_hours(tmp_path: Path):
    mod = _load_mod()
    good = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    good["boss_failover"]["lease_ttl_minutes"] = 5  # below 15
    path = tmp_path / "short.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    errors = mod.validate_assignment(
        MODULE_ROOT / "schema" / "assignment.schema.json", path
    )
    assert any("lease_ttl_minutes" in e for e in errors)

    legacy = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    legacy["boss_failover"]["lease_ttl_hours"] = 12
    del legacy["boss_failover"]["lease_ttl_minutes"]
    path2 = tmp_path / "legacy.json"
    path2.write_text(json.dumps(legacy), encoding="utf-8")
    errors2 = mod.validate_assignment(
        MODULE_ROOT / "schema" / "assignment.schema.json", path2
    )
    assert any("lease_ttl" in e for e in errors2)


def test_lease_ttl_rejects_too_long(tmp_path: Path):
    mod = _load_mod()
    good = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    good["boss_failover"]["lease_ttl_minutes"] = 180  # above 120
    path = tmp_path / "long.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    errors = mod.validate_assignment(
        MODULE_ROOT / "schema" / "assignment.schema.json", path
    )
    assert any("lease_ttl_minutes" in e for e in errors)


def test_claim_queue_must_be_string_list(tmp_path: Path):
    mod = _load_mod()
    good = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    good["boss_failover"]["claim_queue"] = ["ok-agent", 123]
    path = tmp_path / "badq.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    errors = mod.validate_assignment(
        MODULE_ROOT / "schema" / "assignment.schema.json", path
    )
    assert any("claim_queue" in e for e in errors)


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
            lease_ttl_minutes=30,
            idle_window_minutes=20,
            now=now,
        )
        == "noop"
    )
    assert (
        mod.evaluate(
            last_heartbeat=now - timedelta(minutes=35),
            last_github_activity=None,
            lease_ttl_minutes=30,
            idle_window_minutes=20,
            now=now,
        )
        == "vacant"
    )
    assert (
        mod.evaluate(
            last_heartbeat=now - timedelta(minutes=22),
            last_github_activity=now - timedelta(minutes=2),
            lease_ttl_minutes=30,
            idle_window_minutes=20,
            now=now,
        )
        == "nudge_keep_boss"
    )
