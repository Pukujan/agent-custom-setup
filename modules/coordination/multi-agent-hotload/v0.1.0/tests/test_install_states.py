"""SDD (spec/semantics): the install state machine matches SPEC.md section 3.

States are read from the adopter's own records (``adopter_state``); ``DRIFTED``
is derived when a ``READY`` repo's records name older commits than the train;
``CONFLICTED`` is a plan outcome (zero writes, non-zero exit).
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import CGM_SHA, PCM_SHA


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _ready_records(adopter: Path, *, pcm_revision: str = PCM_SHA) -> None:
    """Lay down the three records that make a repo READY."""
    _write(
        adopter / ".coord" / "assignment.json",
        {"pins": {"pcm": {"revision": pcm_revision}, "cgm": {"revision": CGM_SHA}}},
    )
    _write(adopter / "stack-manifest.json", {"schema_version": "agent-stack-train.stack-manifest.v1"})
    _write(adopter / ".oio" / "install-manifest.json", {"version": "0.1.0"})


# --- adopter_state (pure) --------------------------------------------------


def test_absent_when_no_records(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    (adopter / ".content-system").mkdir(parents=True)  # adapter is a precondition only
    assert installer.adopter_state(adopter) == "ABSENT"


def test_recovering_when_a_journal_is_present(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    adopter.mkdir()
    _write(adopter / ".oio" / ".installer-transaction.json", {"started": True})
    assert installer.adopter_state(adopter) == "RECOVERING"


def test_partial_when_coordination_written_but_oio_absent(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    _write(adopter / ".coord" / "assignment.json", {})
    _write(adopter / "stack-manifest.json", {})
    assert installer.adopter_state(adopter) == "PARTIAL"


def test_ready_when_all_records_present(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    _ready_records(adopter)
    assert installer.adopter_state(adopter) == "READY"


# --- drift (pure) ----------------------------------------------------------


def test_lock_drift_when_lock_is_behind_the_mesh(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    _write(
        adopter / ".coord" / "hotload.lock.json",
        {"checkouts": {"pcm": {"commit": "0" * 40}, "cgm": {"commit": CGM_SHA}}},
    )
    drift = installer.lock_drift(adopter, _requires())
    assert drift and "pcm" in drift[0]


def test_assignment_drift_when_assignment_is_behind_the_mesh(tmp_path: Path, installer):
    adopter = tmp_path / "adopter"
    _write(adopter / ".coord" / "assignment.json", {"pins": {"pcm": {"revision": "0" * 40}}})
    drift = installer.assignment_drift(adopter, _requires())
    assert drift and "re-run with --force" in drift[0]


def _requires() -> dict:
    from conftest import mesh_doc

    return mesh_doc()["requires"]


# --- transitions (through run()) ------------------------------------------


def test_run_reports_absent_then_records_ready(
    tmp_path, installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args, capsys,
):
    stub_externals()
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    rc = installer.run(
        run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout())
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "state=ABSENT" in out
    lock = json.loads((adopter / ".coord" / "hotload.lock.json").read_text(encoding="utf-8"))
    assert lock["state"] == "READY"


def test_rerun_keeps_the_edited_assignment(
    tmp_path, installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    """A rerun is a no-op for an edited managed file: it is kept, not clobbered."""
    stub_externals()
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    oio = make_oio_checkout()
    acs_root = make_acs_root()
    assert installer.run(run_args(acs_root, adopter, pcm, cgm, oio)) == 0
    assignment = adopter / ".coord" / "assignment.json"
    edited = json.loads(assignment.read_text(encoding="utf-8"))
    edited["project"] = "operator-edit"
    assignment.write_text(json.dumps(edited), encoding="utf-8")
    before = assignment.read_bytes()

    assert installer.run(run_args(acs_root, adopter, pcm, cgm, oio)) == 0
    assert assignment.read_bytes() == before  # untouched
    lock = json.loads((adopter / ".coord" / "hotload.lock.json").read_text(encoding="utf-8"))
    assert lock["state"] == "READY"


def test_run_reports_drifted_when_records_are_behind_the_train(
    tmp_path, installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args, capsys,
):
    stub_externals()
    adopter = make_adopter()
    _ready_records(adopter, pcm_revision="0" * 40)
    _write(
        adopter / ".coord" / "hotload.lock.json",
        {"checkouts": {"pcm": {"commit": "0" * 40}, "cgm": {"commit": CGM_SHA}}},
    )
    pcm, cgm = make_checkouts()
    rc = installer.run(
        run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout(), dry_run=True)
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "state=DRIFTED" in out
    assert "drift" in out and "re-run with --force" in out


def test_run_reports_conflicted_on_a_foreign_target(
    tmp_path, installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args, capsys,
):
    stub_externals()
    adopter = make_adopter()
    (adopter / "stack-manifest.json").write_text(
        json.dumps({"schema_version": "someone-else.v1"}), encoding="utf-8"
    )
    pcm, cgm = make_checkouts()
    rc = installer.run(
        run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout())
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "state=CONFLICTED" in out
    assert not (adopter / ".coord").exists()
