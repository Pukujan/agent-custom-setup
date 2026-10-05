"""Tests for the multi-agent hotload installer (acs_install.py).

Pure-function tests plus end-to-end runs of ``run()`` with the pack's external
checkers stubbed, so the suite needs no network and no pinned checkouts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = MODULE_ROOT / "scripts" / "acs_install.py"
MODULE_REL = "modules/coordination/multi-agent-hotload/v0.1.0"

PCM_SHA = "a" * 40
CGM_SHA = "b" * 40
ACS_SHA = "c" * 40
OIO_SHA = "d" * 40

CGM_MODULES = [
    "brand-foundation",
    "content-context",
    "writing-direction",
    "human-sounding-writing",
    "human-output-naming",
    "visual-direction",
    "image-generation",
    "html-demo",
]

PINS = {
    "pcm": {"cli_version": "0.6.0", "commit": PCM_SHA},
    "cgm": {"version": "0.5.12", "commit": CGM_SHA, "modules": list(CGM_MODULES)},
    "acs_hotload_module": {"id": "multi-agent-hotload", "version": "0.1.0"},
}


def _load_mod():
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("acs_install", SCRIPT)
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def _mesh_doc() -> dict:
    """Fixture mesh. The installer reads commits from this file, not from pins.json."""
    return {
        "source": "fixture",
        "requires": {
            "project-continuity-modules": {"version": "0.6.0", "commit": PCM_SHA},
            "content-generation-modules": {"version": "0.5.12", "commit": CGM_SHA},
            "agent-custom-setup": {"version": "0.2.0", "commit": ACS_SHA},
            "observational-issue-ops": {"version": "0.1.0", "commit": "d" * 40},
        },
    }


def _fake_acs_root(tmp_path: Path) -> Path:
    root = tmp_path / "acs"
    pack = root / MODULE_REL
    pack.mkdir(parents=True)
    (pack / "pins.json").write_text(json.dumps({"pins": PINS}), encoding="utf-8")
    (root / "stack-mesh.json").write_text(json.dumps(_mesh_doc()), encoding="utf-8")
    return root


def _fake_checkouts(tmp_path: Path) -> tuple[Path, Path]:
    pcm = tmp_path / "pcm-ck"
    cgm = tmp_path / "cgm-ck"
    pcm.mkdir()
    cgm.mkdir()
    return pcm, cgm


def _fake_oio_checkout(tmp_path: Path) -> Path:
    oio = tmp_path / "oio-ck"
    (oio / ".github" / "scripts").mkdir(parents=True)
    (oio / ".github" / "scripts" / "oio_installer.py").write_text("# stub\n", encoding="utf-8")
    return oio


def _stub_externals(monkeypatch, mod) -> None:
    """Make check_pins/hotload_check succeed and report pinned HEADs."""

    def fake_git_head(root):
        name = Path(root).name
        if name == "pcm-ck":
            return PCM_SHA
        if name == "cgm-ck":
            return CGM_SHA
        if name == "oio-ck":
            return OIO_SHA
        return ACS_SHA

    monkeypatch.setattr(mod, "git_head", fake_git_head)
    monkeypatch.setattr(mod, "run_script", lambda argv: 0)
    monkeypatch.setattr(mod, "oio_platform_supported", lambda: (True, ""))


def _adopter(tmp_path: Path, *, with_adapter: bool = True) -> Path:
    adopter = tmp_path / "adopter"
    adopter.mkdir()
    if with_adapter:
        (adopter / ".content-system").mkdir()
    return adopter


# --- pure functions -------------------------------------------------------


def test_commits_agree():
    mod = _load_mod()
    assert mod.commits_agree(PCM_SHA, PCM_SHA)
    assert mod.commits_agree(PCM_SHA, PCM_SHA[:12])
    assert mod.commits_agree(PCM_SHA[:12], PCM_SHA)
    assert not mod.commits_agree(PCM_SHA, CGM_SHA)


def test_verify_checkout_requires_a_path():
    mod = _load_mod()
    errors = mod.verify_checkout(None, PCM_SHA, "pcm")
    assert errors and "not provided" in errors[0]


def test_verify_checkout_rejects_non_git_dir(tmp_path: Path):
    mod = _load_mod()
    plain = tmp_path / "plain"
    plain.mkdir()
    errors = mod.verify_checkout(plain, PCM_SHA, "pcm")
    assert errors and "not a git checkout" in errors[0]


def test_verify_checkout_rejects_wrong_revision(tmp_path: Path):
    mod = _load_mod()
    repo = tmp_path / "repo"
    _git_repo(repo)
    errors = mod.verify_checkout(repo, "0" * 40, "cgm")
    assert errors and "an older version is refused" in errors[0]


def test_verify_checkout_accepts_pinned_revision(tmp_path: Path):
    mod = _load_mod()
    repo = tmp_path / "repo"
    head = _git_repo(repo)
    assert mod.verify_checkout(repo, head, "cgm") == []


def test_build_assignment_repins_from_pins():
    mod = _load_mod()
    example = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    data = mod.build_assignment(example, PINS, "adopter-x")
    assert data["project"] == "adopter-x"
    assert data["pins"]["pcm"]["revision"] == PCM_SHA
    assert data["pins"]["pcm"]["cli_version"] == "0.6.0"
    assert data["pins"]["cgm"]["revision"] == CGM_SHA
    assert data["pins"]["cgm"]["version"] == "0.5.12"
    assert data["pins"]["cgm"]["modules"] == CGM_MODULES
    # No foreign repo's issue URL leaks into the adopter assignment.
    check_in = data["boss_failover"]["check_in"]
    assert "issue_url" not in check_in
    assert check_in["mechanism"] == "claim_file"
    assert data["boss_failover"]["claim_queue"] == []


def test_build_assignment_is_schema_valid():
    jsonschema = __import__("jsonschema", fromlist=["Draft202012Validator"])
    mod = _load_mod()
    example = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (MODULE_ROOT / "schema" / "assignment.schema.json").read_text(encoding="utf-8")
    )
    data = mod.build_assignment(example, PINS, "adopter-x")
    jsonschema.Draft202012Validator(schema).validate(data)


def test_generated_assignment_passes_pack_validator(tmp_path: Path):
    """The installer's output must satisfy hotload_check's own pin/failover rules."""
    from importlib.util import module_from_spec, spec_from_file_location

    mod = _load_mod()
    spec = spec_from_file_location("hotload_check", MODULE_ROOT / "scripts" / "hotload_check.py")
    assert spec and spec.loader
    check = module_from_spec(spec)
    spec.loader.exec_module(check)

    example = json.loads(
        (MODULE_ROOT / "examples" / "assignment.example.json").read_text(encoding="utf-8")
    )
    # The installer overlays stack-mesh.json onto pins.json before it writes.
    real_pins = mod.load_json(MODULE_ROOT / "pins.json")["pins"]
    mesh = mod.load_json(MODULE_ROOT.parents[3] / "stack-mesh.json")["requires"]
    real_pins["pcm"]["commit"] = mesh["project-continuity-modules"]["commit"]
    real_pins["pcm"]["cli_version"] = mesh["project-continuity-modules"]["version"]
    real_pins["cgm"]["commit"] = mesh["content-generation-modules"]["commit"]
    real_pins["cgm"]["version"] = mesh["content-generation-modules"]["version"]
    generated = mod.build_assignment(example, real_pins, "adopter-x")
    out = tmp_path / "assignment.json"
    out.write_text(json.dumps(generated), encoding="utf-8")
    errors = check.validate_assignment(MODULE_ROOT / "schema" / "assignment.schema.json", out)
    assert errors == [], errors


def test_build_lock_has_no_absolute_paths(tmp_path: Path):
    mod = _load_mod()
    acs_root = _fake_acs_root(tmp_path)
    checkouts = {"pcm": {"commit": PCM_SHA, "verified": True},
                 "cgm": {"commit": CGM_SHA, "verified": True}}
    lock = mod.build_lock(PINS, acs_root, checkouts, validated=True)
    assert lock["schema"] == "acs.hotload.lock.v1"
    assert lock["hotload_check"] == "OK"
    blob = json.dumps(lock)
    assert str(tmp_path) not in blob
    assert ":\\" not in blob and '"/' not in blob


def test_write_json_atomic_leaves_no_temp_files(tmp_path: Path):
    mod = _load_mod()
    target = tmp_path / "sub" / "out.json"
    mod.write_json_atomic(target, {"a": 1}, root=tmp_path)
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    mod.write_json_atomic(target, {"a": 2}, root=tmp_path)
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 2}
    assert [p.name for p in target.parent.iterdir()] == ["out.json"]


def test_write_json_atomic_refuses_to_escape_root(tmp_path: Path):
    mod = _load_mod()
    adopter = tmp_path / "adopter"
    adopter.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (adopter / ".coord").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted on this platform")
    with pytest.raises(ValueError):
        mod.write_json_atomic(
            adopter / ".coord" / "assignment.json", {"x": 1}, root=adopter
        )
    assert list(outside.iterdir()) == []


# --- end-to-end run() -----------------------------------------------------


def _run_args(mod, acs_root, adopter, pcm, cgm, oio=None, **over):
    base = dict(
        adopter_root=adopter,
        acs_root=acs_root,
        pcm_root=pcm,
        cgm_root=cgm,
        oio_root=oio,
        project_name=None,
        project_id=None,
        dry_run=False,
        force=False,
    )
    base.update(over)
    return mod.argparse.Namespace(**base)


def test_run_success_writes_surface(tmp_path: Path, monkeypatch):
    mod = _load_mod()
    _stub_externals(monkeypatch, mod)
    acs_root = _fake_acs_root(tmp_path)
    pcm, cgm = _fake_checkouts(tmp_path)
    oio = _fake_oio_checkout(tmp_path)
    adopter = _adopter(tmp_path)

    rc = mod.run(_run_args(mod, acs_root, adopter, pcm, cgm, oio))
    assert rc == 0
    assignment = json.loads((adopter / ".coord" / "assignment.json").read_text(encoding="utf-8"))
    lock = json.loads((adopter / ".coord" / "hotload.lock.json").read_text(encoding="utf-8"))
    assert assignment["pins"]["cgm"]["revision"] == CGM_SHA
    assert lock["hotload_check"] == "OK"
    assert lock["state"] == "READY"
    assert lock["oio_install"] == "OK"
    assert lock["checkouts"]["pcm"]["verified"] is True
    assert lock["checkouts"]["oio"]["verified"] is True


def test_run_writes_empty_pin_manifest(tmp_path: Path, monkeypatch):
    """Train routing: every component pinned, every pin empty (follow the train)."""
    mod = _load_mod()
    _stub_externals(monkeypatch, mod)
    acs_root = _fake_acs_root(tmp_path)
    pcm, cgm = _fake_checkouts(tmp_path)
    oio = _fake_oio_checkout(tmp_path)
    adopter = _adopter(tmp_path)

    assert mod.run(_run_args(mod, acs_root, adopter, pcm, cgm, oio)) == 0
    manifest = json.loads((adopter / "stack-manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "agent-stack-train.stack-manifest.v1"
    assert manifest["release_train"] == "current"
    assert set(manifest["pins"]) == {
        "project-continuity-modules",
        "content-generation-modules",
        "agent-custom-setup",
        "observational-issue-ops",
    }
    assert all(pin == {} for pin in manifest["pins"].values())
    # No install-day version leaked into the manifest.
    assert PCM_SHA not in json.dumps(manifest)


def test_run_refuses_foreign_manifest(tmp_path: Path, monkeypatch):
    mod = _load_mod()
    _stub_externals(monkeypatch, mod)
    acs_root = _fake_acs_root(tmp_path)
    pcm, cgm = _fake_checkouts(tmp_path)
    oio = _fake_oio_checkout(tmp_path)
    adopter = _adopter(tmp_path)
    foreign = {"schema_version": "someone-else.v1", "pins": {"pcm": "0.6.0"}}
    (adopter / "stack-manifest.json").write_text(json.dumps(foreign), encoding="utf-8")

    rc = mod.run(_run_args(mod, acs_root, adopter, pcm, cgm, oio))
    assert rc == 1
    assert json.loads((adopter / "stack-manifest.json").read_text(encoding="utf-8")) == foreign
    assert not (adopter / ".coord").exists()


def test_run_partial_without_oio_root(tmp_path: Path, monkeypatch):
    mod = _load_mod()
    _stub_externals(monkeypatch, mod)
    acs_root = _fake_acs_root(tmp_path)
    pcm, cgm = _fake_checkouts(tmp_path)
    adopter = _adopter(tmp_path)

    rc = mod.run(_run_args(mod, acs_root, adopter, pcm, cgm, None))
    assert rc == 1
    lock = json.loads((adopter / ".coord" / "hotload.lock.json").read_text(encoding="utf-8"))
    assert lock["state"] == "PARTIAL"
    assert lock["oio_install"] == "not_run"
    # The coordination surface is still written and valid.
    assert (adopter / ".coord" / "assignment.json").is_file()
    assert (adopter / "stack-manifest.json").is_file()


def test_run_partial_when_oio_unsupported(tmp_path: Path, monkeypatch):
    """A platform OIO cannot run on reports PARTIAL, never a fake OK."""
    mod = _load_mod()
    _stub_externals(monkeypatch, mod)
    monkeypatch.setattr(
        mod, "oio_platform_supported", lambda: (False, "os.O_NOFOLLOW is unavailable")
    )
    acs_root = _fake_acs_root(tmp_path)
    pcm, cgm = _fake_checkouts(tmp_path)
    oio = _fake_oio_checkout(tmp_path)
    adopter = _adopter(tmp_path)

    rc = mod.run(_run_args(mod, acs_root, adopter, pcm, cgm, oio))
    assert rc == 1
    lock = json.loads((adopter / ".coord" / "hotload.lock.json").read_text(encoding="utf-8"))
    assert lock["state"] == "PARTIAL"


def test_run_dry_run_writes_nothing(tmp_path: Path, monkeypatch):
    mod = _load_mod()
    _stub_externals(monkeypatch, mod)
    acs_root = _fake_acs_root(tmp_path)
    pcm, cgm = _fake_checkouts(tmp_path)
    oio = _fake_oio_checkout(tmp_path)
    adopter = _adopter(tmp_path)

    rc = mod.run(_run_args(mod, acs_root, adopter, pcm, cgm, oio, dry_run=True))
    assert rc == 0
    assert not (adopter / ".coord").exists()
    assert not (adopter / "stack-manifest.json").exists()


def test_run_missing_adapter_fails_closed(tmp_path: Path, monkeypatch):
    mod = _load_mod()
    _stub_externals(monkeypatch, mod)
    acs_root = _fake_acs_root(tmp_path)
    pcm, cgm = _fake_checkouts(tmp_path)
    oio = _fake_oio_checkout(tmp_path)
    adopter = _adopter(tmp_path, with_adapter=False)

    rc = mod.run(_run_args(mod, acs_root, adopter, pcm, cgm, oio))
    assert rc == 1
    assert not (adopter / ".coord").exists()


def test_run_missing_checkout_fails_closed(tmp_path: Path, monkeypatch):
    mod = _load_mod()
    _stub_externals(monkeypatch, mod)
    acs_root = _fake_acs_root(tmp_path)
    pcm, _ = _fake_checkouts(tmp_path)
    oio = _fake_oio_checkout(tmp_path)
    adopter = _adopter(tmp_path)

    rc = mod.run(_run_args(mod, acs_root, adopter, pcm, None, oio))
    assert rc == 1
    assert not (adopter / ".coord").exists()


def test_run_keeps_existing_files_without_force(tmp_path: Path, monkeypatch):
    mod = _load_mod()
    _stub_externals(monkeypatch, mod)
    acs_root = _fake_acs_root(tmp_path)
    pcm, cgm = _fake_checkouts(tmp_path)
    oio = _fake_oio_checkout(tmp_path)
    adopter = _adopter(tmp_path)
    coord = adopter / ".coord"
    coord.mkdir()
    sentinel = {"project": "hand-edited"}
    (coord / "assignment.json").write_text(json.dumps(sentinel), encoding="utf-8")

    rc = mod.run(_run_args(mod, acs_root, adopter, pcm, cgm, oio))
    assert rc == 0
    kept = json.loads((coord / "assignment.json").read_text(encoding="utf-8"))
    assert kept == sentinel  # untouched without --force
    assert (coord / "hotload.lock.json").is_file()


def test_run_force_overwrites(tmp_path: Path, monkeypatch):
    mod = _load_mod()
    _stub_externals(monkeypatch, mod)
    acs_root = _fake_acs_root(tmp_path)
    pcm, cgm = _fake_checkouts(tmp_path)
    oio = _fake_oio_checkout(tmp_path)
    adopter = _adopter(tmp_path)
    coord = adopter / ".coord"
    coord.mkdir()
    (coord / "assignment.json").write_text('{"project": "hand-edited"}', encoding="utf-8")

    rc = mod.run(_run_args(mod, acs_root, adopter, pcm, cgm, oio, force=True))
    assert rc == 0
    data = json.loads((coord / "assignment.json").read_text(encoding="utf-8"))
    assert data["project"] == "adopter"


def test_run_fails_closed_when_hotload_check_fails(tmp_path: Path, monkeypatch):
    mod = _load_mod()
    acs_root = _fake_acs_root(tmp_path)
    pcm, cgm = _fake_checkouts(tmp_path)
    oio = _fake_oio_checkout(tmp_path)
    adopter = _adopter(tmp_path)

    monkeypatch.setattr(mod, "git_head", lambda root: {
        "pcm-ck": PCM_SHA, "cgm-ck": CGM_SHA, "oio-ck": OIO_SHA}.get(Path(root).name, ACS_SHA))
    monkeypatch.setattr(mod, "oio_platform_supported", lambda: (True, ""))
    calls = {"n": 0}

    def run_script(argv):
        calls["n"] += 1
        return 0 if calls["n"] == 1 else 1  # check_pins OK, hotload_check FAIL

    monkeypatch.setattr(mod, "run_script", run_script)
    rc = mod.run(_run_args(mod, acs_root, adopter, pcm, cgm, oio))
    assert rc == 1
    # A failed final check must not leave a partial install behind.
    assert not (adopter / ".coord" / "assignment.json").exists()
    assert not (adopter / ".coord" / "hotload.lock.json").exists()
    assert not (adopter / "stack-manifest.json").exists()


def test_build_stack_manifest_empty_pins():
    mod = _load_mod()
    manifest = mod.build_stack_manifest(_mesh_doc(), "adopter-x")
    assert manifest["adopter"] == "adopter-x"
    assert manifest["source"] == "fixture"
    assert manifest["pins"] == {
        "agent-custom-setup": {},
        "content-generation-modules": {},
        "observational-issue-ops": {},
        "project-continuity-modules": {},
    }


def test_oio_platform_probe_matches_capabilities():
    mod = _load_mod()
    supported, why = mod.oio_platform_supported()
    expected = (
        {os.open, os.mkdir, os.stat, os.unlink, os.rename}.issubset(os.supports_dir_fd)
        and hasattr(os, "O_NOFOLLOW")
        and hasattr(os, "O_DIRECTORY")
    )
    assert supported is expected
    if not supported:
        assert why


def test_module_has_no_hardcoded_pins():
    """The installer must read pins.json, never bake pin literals (drift surface)."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "0.5.12" not in text
    assert "6831f91e" not in text
    assert "4e23854" not in text
