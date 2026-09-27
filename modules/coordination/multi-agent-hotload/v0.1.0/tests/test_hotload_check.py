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
    import os
    cgm = Path("/workspace/cgm-051")
    adopter = MODULE_ROOT.parents[3]
    args = [sys.executable, str(SCRIPT)]
    if (cgm / "scripts" / "validate_content_system.py").is_file():
        args.extend(["--cgm-root", str(cgm), "--adopter-root", str(adopter)])
    else:
        # Schema-only fallback when CGM pin tree is absent on the runner
        env = os.environ.copy()
        env["HOTLOAD_SKIP_CGM_VALIDATE"] = "1"
        proc = subprocess.run(args, capture_output=True, text=True, check=False, env=env)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "hotload_check: OK" in proc.stdout or "WARN skip_cgm_validate" in proc.stdout
        return
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "hotload_check: OK" in proc.stdout
    assert "cgm_validate=VALID" in proc.stdout


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


def test_pins_reject_slim_cgm_subset(tmp_path: Path):
    """Alex binding: HSW+writing-direction only is an incomplete install."""
    mod = _load_mod()
    good = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    good["pins"]["cgm"]["modules"] = [
        "human-sounding-writing",
        "writing-direction",
    ]
    path = tmp_path / "slim.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    errors = mod.validate_assignment(
        MODULE_ROOT / "schema" / "assignment.schema.json", path
    )
    assert any("FULL CGM" in e or "seven" in e or "missing" in e for e in errors), errors


def test_pins_require_full_pcm_features(tmp_path: Path):
    mod = _load_mod()
    good = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    good["pins"]["pcm"]["required_features"] = ["checkout_continuity_checkpoints"]
    path = tmp_path / "thin-pcm.json"
    path.write_text(json.dumps(good), encoding="utf-8")
    errors = mod.validate_assignment(
        MODULE_ROOT / "schema" / "assignment.schema.json", path
    )
    assert any("required_features" in e or "FULL PCM" in e for e in errors), errors


def test_example_pins_are_full_stacks():
    mod = _load_mod()
    data = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    assert data["pins"]["cgm"]["version"] == "0.5.1"
    assert data["pins"]["cgm"]["revision"].startswith("9874b26")
    assert data["pins"]["pcm"]["revision"].startswith("4e23854")
    assert set(mod.REQUIRED_CGM_MODULES).issubset(
        {
            (m[len("modules/") :] if str(m).startswith("modules/") else str(m))
            for m in data["pins"]["cgm"]["modules"]
        }
    )


def test_cli_ok_with_cgm_validate():
    """Install check must run CGM validate_content_system (no HSW-only script)."""
    import os
    cgm = Path("/workspace/cgm-051")
    if not (cgm / "scripts" / "validate_content_system.py").is_file():
        import pytest
        pytest.skip("cgm-051 checkout not present on this machine")
    adopter = MODULE_ROOT.parents[3]
    env = os.environ.copy()
    env.pop("HOTLOAD_SKIP_CGM_VALIDATE", None)
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--cgm-root",
            str(cgm),
            "--adopter-root",
            str(adopter),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "hotload_check: OK" in proc.stdout
    assert "cgm_validate=VALID" in proc.stdout
    assert "WRITING_ROUTING" in proc.stdout
