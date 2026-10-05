"""Differential (offline shape): the adopter manifest agrees with the pack mesh.

The **live** comparison — the pack's ``stack-mesh.json`` against the certified
release train, and the adopter manifest against ``check_manifest.py`` — runs in
``tests/test_train_parity.py`` (network) and the train's own ``check-adopter.yml``
/ ``require-mesh.yml`` CI. Here we prove the offline shape: every mesh component
is pinned, every pin is empty (follow the train), and the schema is the train's.
"""

from __future__ import annotations

import json

import pytest

from conftest import mesh_doc

TRAIN_SCHEMA = "agent-stack-train.stack-manifest.v1"


def test_written_manifest_pins_exactly_the_mesh_components(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    stub_externals()
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    mesh = mesh_doc()
    rc = installer.run(
        run_args(make_acs_root(mesh), adopter, pcm, cgm, make_oio_checkout())
    )
    assert rc == 0
    manifest = json.loads((adopter / "stack-manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["pins"]) == set(mesh["requires"])


def test_written_manifest_pins_are_empty(
    installer, make_adopter, make_checkouts, make_oio_checkout, make_acs_root,
    stub_externals, run_args,
):
    stub_externals()
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    assert installer.run(
        run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout())
    ) == 0
    manifest = json.loads((adopter / "stack-manifest.json").read_text(encoding="utf-8"))
    assert manifest["pins"] and all(pin == {} for pin in manifest["pins"].values())


def test_written_manifest_uses_the_train_schema_and_source(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    stub_externals()
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    mesh = mesh_doc()
    assert installer.run(
        run_args(make_acs_root(mesh), adopter, pcm, cgm, make_oio_checkout())
    ) == 0
    manifest = json.loads((adopter / "stack-manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == TRAIN_SCHEMA
    assert manifest["source"] == mesh["source"]
    assert manifest["release_train"] == installer.TRAIN_RELEASE
    assert manifest["adopter"] == adopter.name


def test_written_manifest_carries_no_install_day_version(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    """A pin is never frozen to install-day versions (SPEC.md section 1)."""
    from conftest import CGM_SHA, OIO_SHA, PCM_SHA

    stub_externals()
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    assert installer.run(
        run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout())
    ) == 0
    blob = (adopter / "stack-manifest.json").read_text(encoding="utf-8")
    for sha in (PCM_SHA, CGM_SHA, OIO_SHA):
        assert sha not in blob
    assert "0.5.12" not in blob and "0.6.0" not in blob


def test_build_stack_manifest_refuses_an_empty_mesh(installer):
    with pytest.raises(ValueError):
        installer.build_stack_manifest({"source": "x", "requires": {}}, "adopter-x")
    with pytest.raises(ValueError):
        installer.build_stack_manifest({}, "adopter-x")
