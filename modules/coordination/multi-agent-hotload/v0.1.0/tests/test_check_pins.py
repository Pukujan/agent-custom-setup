"""Tests for the hotload pin drift check (single-source manifest, fail closed)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parents[3]
SCRIPT = MODULE_ROOT / "scripts" / "check_pins.py"


def _run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_repo(tmp_path: Path) -> Path:
    """Copy the manifest and every projection into an isolated tree."""
    manifest = json.loads((MODULE_ROOT / "pins.json").read_text(encoding="utf-8"))
    root = tmp_path / "repo"
    for entry in manifest["projections"]:
        rel = entry["file"]
        src = REPO_ROOT / rel
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    (root / "pins.json").parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(MODULE_ROOT / "pins.json", root / "pins.json")
    return root


def test_pins_manifest_is_self_consistent():
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("check_pins", SCRIPT)
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    manifest = json.loads((MODULE_ROOT / "pins.json").read_text(encoding="utf-8"))
    assert mod.check_manifest(manifest) == []


def test_check_pins_passes_on_aligned_tree(tmp_path: Path):
    root = _seed_repo(tmp_path)
    proc = _run(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "check_pins: OK" in proc.stdout


def test_check_pins_fails_on_drifted_sha(tmp_path: Path):
    root = _seed_repo(tmp_path)
    # HOTLOAD.md projects cgm.commit; swap the pinned SHA for a foreign one.
    target = root / "modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md"
    text = target.read_text(encoding="utf-8")
    target.write_text(
        text.replace(
            "c069613ca8b3e02bcf5aba1960160583537f8a3a",
            "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        ),
        encoding="utf-8",
    )
    proc = _run(root)
    assert proc.returncode == 1
    assert "check_pins: FAIL" in proc.stdout
    assert "HOTLOAD.md" in proc.stdout and "deadbeef" in proc.stdout


def test_check_pins_fails_on_drifted_version(tmp_path: Path):
    root = _seed_repo(tmp_path)
    target = root / "modules/coordination/multi-agent-hotload/v0.1.0/ROLES.md"
    text = target.read_text(encoding="utf-8")
    target.write_text(text.replace("0.5.7", "0.5.1"), encoding="utf-8")
    proc = _run(root)
    assert proc.returncode == 1
    assert "check_pins: FAIL" in proc.stdout
    assert "ROLES.md" in proc.stdout


def test_check_pins_fails_on_superseded_value_even_when_canonical_present(tmp_path: Path):
    root = _seed_repo(tmp_path)
    target = root / "modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md"
    text = target.read_text(encoding="utf-8")
    # Canonical value stays; a superseded one is appended (the "carries both" case).
    target.write_text(text + "\n(legacy) seven modules\n", encoding="utf-8")
    proc = _run(root)
    assert proc.returncode == 1
    assert "check_pins: FAIL" in proc.stdout
    assert "superseded" in proc.stdout


def test_check_pins_fails_on_missing_projection_file(tmp_path: Path):
    root = _seed_repo(tmp_path)
    (root / "registry.json").unlink()
    proc = _run(root)
    assert proc.returncode == 1
    assert "check_pins: FAIL" in proc.stdout
    assert "registry.json" in proc.stdout
