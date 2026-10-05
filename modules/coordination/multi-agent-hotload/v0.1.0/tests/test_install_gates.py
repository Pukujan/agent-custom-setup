"""TDD (unit): the per-artifact gate classifies each path kind (SPEC.md section 4).

Every row of the gate table is exercised directly against ``gate_plan`` and
``classify_owned`` so a regression in classification is caught without a full
install. The invariant that matters: a refusal yields *zero* writes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _target(adopter: Path, rel: str, data: object) -> tuple[Path, object]:
    return adopter / rel, data


def test_absent_path_is_created(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    adopter.mkdir()
    data = {"schema_version": "agent-stack-train.stack-manifest.v1"}
    to_write, kept, refusals = installer.gate_plan(
        [_target(adopter, "stack-manifest.json", data)], adopter, force=False
    )
    assert [p.name for p, _ in to_write] == ["stack-manifest.json"]
    assert kept == [] and refusals == []


def test_our_file_is_kept_without_force(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    (adopter / ".coord").mkdir(parents=True)
    existing = adopter / ".coord" / "assignment.json"
    existing.write_text('{"project": "hand-edited"}', encoding="utf-8")
    to_write, kept, refusals = installer.gate_plan(
        [_target(adopter, ".coord/assignment.json", {"project": "regenerated"})],
        adopter,
        force=False,
    )
    assert to_write == [] and refusals == []
    assert [p.name for p, _ in kept] == ["assignment.json"]
    assert json.loads(existing.read_text(encoding="utf-8")) == {"project": "hand-edited"}


def test_our_file_is_regenerated_with_force(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    (adopter / ".coord").mkdir(parents=True)
    (adopter / ".coord" / "assignment.json").write_text("{}", encoding="utf-8")
    to_write, kept, refusals = installer.gate_plan(
        [_target(adopter, ".coord/assignment.json", {"project": "regenerated"})],
        adopter,
        force=True,
    )
    assert kept == [] and refusals == []
    assert [p.name for p, _ in to_write] == ["assignment.json"]


def test_foreign_identical_file_is_adopted(tmp_path: Path, installer):
    """A foreign file byte-identical to what we would write is adopted, not refused."""
    adopter = tmp_path / "adopter"
    adopter.mkdir()
    data = {"schema_version": "agent-stack-train.stack-manifest.v1", "pins": {}}
    target = adopter / "stack-manifest.json"
    target.write_bytes(installer.render_json_bytes(data))
    to_write, kept, refusals = installer.gate_plan(
        [(target, data)], adopter, force=False
    )
    assert to_write == [] and refusals == []
    assert [p.name for p, _ in kept] == ["stack-manifest.json"]


def test_foreign_different_file_is_refused(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    adopter.mkdir()
    target = adopter / "stack-manifest.json"
    target.write_text(json.dumps({"schema_version": "someone-else.v1"}), encoding="utf-8")
    to_write, kept, refusals = installer.gate_plan(
        [(target, {"schema_version": "agent-stack-train.stack-manifest.v1"})],
        adopter,
        force=False,
    )
    assert to_write == [] and kept == []
    assert len(refusals) == 1 and "stack-manifest.json" in refusals[0]


def test_symlink_target_is_refused(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    adopter.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    link = adopter / "stack-manifest.json"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted on this platform")
    to_write, kept, refusals = installer.gate_plan(
        [(link, {"schema_version": "agent-stack-train.stack-manifest.v1"})],
        adopter,
        force=False,
    )
    assert to_write == [] and kept == []
    assert len(refusals) == 1 and "not a regular file" in refusals[0]


def test_directory_target_is_refused(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    (adopter / "stack-manifest.json").mkdir(parents=True)
    to_write, kept, refusals = installer.gate_plan(
        [(adopter / "stack-manifest.json", {"a": 1})], adopter, force=False
    )
    assert to_write == [] and kept == []
    assert len(refusals) == 1 and "not a regular file" in refusals[0]


def test_one_refusal_blocks_the_whole_plan(tmp_path: Path, installer):
    """A single unresolved path means zero writes, never a partial apply."""
    adopter = tmp_path / "adopter"
    (adopter / ".coord").mkdir(parents=True)
    (adopter / ".coord" / "assignment.json").write_text("{}", encoding="utf-8")
    foreign = adopter / "stack-manifest.json"
    foreign.write_text('{"schema_version": "someone-else.v1"}', encoding="utf-8")
    targets = [
        _target(adopter, ".coord/assignment.json", {"project": "x"}),
        (foreign, {"schema_version": "agent-stack-train.stack-manifest.v1"}),
    ]
    to_write, kept, refusals = installer.gate_plan(targets, adopter, force=False)
    assert refusals and not to_write


def test_classify_owned_accepts_coord_files(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    (adopter / ".coord").mkdir(parents=True)
    ours = adopter / ".coord" / "hotload.lock.json"
    ours.write_text("{}", encoding="utf-8")
    assert installer.classify_owned(ours, adopter) is True


def test_classify_owned_accepts_manifest_by_schema(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    adopter.mkdir()
    ours = adopter / "stack-manifest.json"
    ours.write_text(
        json.dumps({"schema_version": "agent-stack-train.stack-manifest.v1"}), encoding="utf-8"
    )
    assert installer.classify_owned(ours, adopter) is True


def test_classify_owned_rejects_foreign_schema(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    adopter.mkdir()
    foreign = adopter / "stack-manifest.json"
    foreign.write_text('{"schema_version": "someone-else.v1"}', encoding="utf-8")
    assert installer.classify_owned(foreign, adopter) is False


def test_render_json_bytes_is_stable_and_lf(installer):
    """Equality checks must not depend on platform newline translation."""
    data = {"b": 2, "a": 1}
    first = installer.render_json_bytes(data)
    second = installer.render_json_bytes(json.loads(first.decode("utf-8")))
    assert first == second
    assert b"\r\n" not in first
    assert first.endswith(b"\n")
