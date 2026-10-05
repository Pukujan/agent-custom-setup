"""Differential check: the pack's mesh and the adopter manifest against the train.

Two layers:

* **Offline** (always runs): the pack's ``stack-mesh.json`` and a manifest built
  from it agree with each other and with the train's component set, and every
  component carries a version and a commit.
* **Live** (skipped when the train is unreachable): the pack is not behind the
  certified release train. This is the check that would have caught the
  2026-10-01 snapshot staying on PCM 0.6.0 after 0.7.0 shipped.

The live layer needs the network, so it is skipped in an offline CI; the train's
own ``require-mesh.yml`` / ``check-adopter.yml`` run the live comparison in the
repos that call them.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parents[3]
MESH_FILE = REPO_ROOT / "stack-mesh.json"
TRAIN_URL = "https://raw.githubusercontent.com/Pukujan/agent-stack-train/main/stack-releases.json"
COMPONENTS = {
    "project-continuity-modules",
    "content-generation-modules",
    "agent-custom-setup",
    "observational-issue-ops",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _live_train() -> dict | None:
    try:
        with urllib.request.urlopen(TRAIN_URL, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


def _installer():
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("acs_install", MODULE_ROOT / "scripts" / "acs_install.py")
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- offline ---------------------------------------------------------------


def test_mesh_requires_every_component():
    mesh = _load(MESH_FILE)
    requires = mesh.get("requires")
    assert isinstance(requires, dict)
    assert set(requires) == COMPONENTS
    for name, entry in requires.items():
        assert entry.get("version"), f"{name} has no version"
        assert entry.get("commit"), f"{name} has no commit"


def test_manifest_pins_match_mesh_components():
    """The manifest the installer writes pins exactly the mesh's components."""
    mod = _installer()
    mesh = _load(MESH_FILE)
    manifest = mod.build_stack_manifest(mesh, "adopter-x")
    assert set(manifest["pins"]) == set(mesh["requires"])
    assert all(pin == {} for pin in manifest["pins"].values())


def test_manifest_shape_is_train_schema():
    mod = _installer()
    manifest = mod.build_stack_manifest(_load(MESH_FILE), "adopter-x")
    assert manifest["schema_version"] == "agent-stack-train.stack-manifest.v1"
    assert manifest["release_train"] == mod.TRAIN_RELEASE
    assert manifest["source"] == _load(MESH_FILE)["source"]


# --- live (skipped offline) ------------------------------------------------


def test_pack_is_not_behind_the_live_train():
    train = _live_train()
    if train is None:
        pytest.skip("release train unreachable; live differential needs the network")
    certified = train.get("certified", {})
    requires = _load(MESH_FILE).get("requires", {})
    assert set(certified) == COMPONENTS
    for name, entry in sorted(certified.items()):
        local = requires.get(name) or {}
        assert local.get("version") == entry.get("version"), f"{name}: version is behind the train"
        assert local.get("commit") == entry.get("commit"), f"{name}: commit is behind the train"


def test_release_train_constant_is_current():
    train = _live_train()
    if train is None:
        pytest.skip("release train unreachable; live differential needs the network")
    assert _installer().TRAIN_RELEASE == train.get("release_train")
