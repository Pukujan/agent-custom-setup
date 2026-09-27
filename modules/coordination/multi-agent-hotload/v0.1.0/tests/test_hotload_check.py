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


def _find_cgm_for_tests() -> Path | None:
    candidates = [
        Path("/workspace/cgm-054"),
        Path("/workspace/cgm-053"),
        Path("/workspace/cgm-051"),
        Path(r"D:\claude\content-generation-modules"),
        Path.home() / "content-generation-modules",
    ]
    env = __import__("os").environ.get("CGM_ROOT")
    if env:
        candidates.insert(0, Path(env))
    for cand in candidates:
        if (cand / "scripts" / "validate_content_system.py").is_file():
            return cand
    return None


def test_cli_ok():
    import os
    cgm = _find_cgm_for_tests()
    adopter = MODULE_ROOT.parents[3]
    args = [sys.executable, str(SCRIPT)]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if cgm is not None:
        args.extend(["--cgm-root", str(cgm), "--adopter-root", str(adopter)])
        proc = subprocess.run(args, capture_output=True, text=True, check=False, env=env)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "hotload_check: OK" in proc.stdout
        assert "cgm_validate=VALID" in proc.stdout
        return
    env["HOTLOAD_SKIP_CGM_VALIDATE"] = "1"
    proc = subprocess.run(args, capture_output=True, text=True, check=False, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "hotload_check: OK" in proc.stdout or "WARN skip_cgm_validate" in proc.stdout


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
    assert data["pins"]["cgm"]["version"] == "0.5.4"
    assert data["pins"]["cgm"]["revision"].startswith("c95d73a")
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
    cgm = _find_cgm_for_tests()
    if cgm is None:
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
    assert "WRITING_ROUTING" in proc.stdout or "writing-routing" in proc.stdout or "acs_prompt_inject" in proc.stdout
    assert "acs_prompt_inject" in proc.stdout
    assert (MODULE_ROOT / "PROMPT_INJECT.md").is_file()
    inject = (MODULE_ROOT / "PROMPT_INJECT.md").read_text(encoding="utf-8")
    assert "MUST load" in inject or "required_load" in inject or "writing-direction" in inject


def test_cgm_pin_constants_054():
    mod = _load_mod()
    assert mod.CGM_PIN_VERSION == "0.5.4"
    assert mod.CGM_PIN_REVISION.startswith("c95d73a")
    assert mod.CGM_PIN_REVISION == "c95d73a0ce072a6d7173ce4848621a25cdf1cc7e"
    assert mod.CGM_PIN_REVISION_PREFIX == "c95d73a"


def test_apply_acs_prompt_inject_writes_file(tmp_path: Path):
    """When CGM pin is available, apply_acs_prompt_inject writes PROMPT_INJECT.md."""
    import os
    cgm = _find_cgm_for_tests()
    if cgm is None:
        import pytest
        pytest.skip("CGM checkout not present on this machine")
    mod = _load_mod()
    # ensure pin SHA matches (caller responsibility in live install)
    sha = mod.cgm_checkout_sha(cgm)
    if sha is None or not sha.startswith(mod.CGM_PIN_REVISION_PREFIX):
        import pytest
        pytest.skip(f"CGM checkout HEAD={sha} not at pin {mod.CGM_PIN_REVISION}")
    out_root = tmp_path
    text, notes = mod.apply_acs_prompt_inject(cgm, out_root)
    assert text and "MUST load" in text
    assert (out_root / "PROMPT_INJECT.md").is_file()
    body = (out_root / "PROMPT_INJECT.md").read_text(encoding="utf-8")
    assert "writing-direction" in body
    assert "human-sounding-writing" in body or "hsw" in body.lower()
    assert any("wrote" in n for n in notes)


def test_external_research_gate_heading_present():
    """Heading-only assertion; CGM pin/modules unchanged."""
    mod = _load_mod()
    errors = mod.check_external_research_gate(MODULE_ROOT)
    assert errors == [], errors
    assert mod.CGM_PIN_VERSION == "0.5.4"
    assert mod.CGM_PIN_REVISION.startswith("c95d73a")
    assert set(mod.REQUIRED_CGM_MODULES) == {
        "brand-foundation",
        "content-context",
        "writing-direction",
        "human-sounding-writing",
        "visual-direction",
        "image-generation",
        "html-demo",
    }


def test_external_research_gate_fails_when_heading_removed(tmp_path: Path):
    mod = _load_mod()
    for name in ("BEHAVIOR.md", "HOTLOAD.md"):
        src = (MODULE_ROOT / name).read_text(encoding="utf-8")
        (tmp_path / name).write_text(
            src.replace("External research gate", "X-research-placeholder"),
            encoding="utf-8",
        )
    policy = tmp_path / "POLICY.md"
    policy.write_text("# POLICY\n\nNo gate here.\n", encoding="utf-8")
    errors = mod.check_external_research_gate(tmp_path, policy_path=policy)
    assert errors
    assert any("External research gate" in e or "missing heading" in e for e in errors)

