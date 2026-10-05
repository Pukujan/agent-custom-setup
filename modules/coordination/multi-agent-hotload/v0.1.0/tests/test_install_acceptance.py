"""PDD (acceptance): a fresh adopter reaches READY; a conflicted repo is refused.

These are the end-to-end promises of SPEC.md sections 2, 3 and 7: the happy path
completes and records state, and every unhappy path fails closed with a report
that names the cause — never a fake OK.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_fresh_adopter_reaches_ready(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args, capsys,
):
    stub_externals()
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    rc = installer.run(run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout()))
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK (state=READY)" in out
    assert (adopter / ".coord" / "assignment.json").is_file()
    assert (adopter / "stack-manifest.json").is_file()
    lock = json.loads((adopter / ".coord" / "hotload.lock.json").read_text(encoding="utf-8"))
    assert lock["state"] == "READY"
    assert lock["hotload_check"] == "OK"
    assert lock["oio_install"] == "OK"
    assert lock["checkouts"]["pcm"]["verified"] is True
    assert lock["checkouts"]["cgm"]["verified"] is True
    assert lock["checkouts"]["oio"]["verified"] is True


def test_conflicted_repo_is_refused_with_a_clear_report(
    tmp_path, installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args, capsys,
):
    stub_externals()
    adopter = make_adopter()
    foreign = {"schema_version": "someone-else.v1", "pins": {"pcm": "0.6.0"}}
    (adopter / "stack-manifest.json").write_text(json.dumps(foreign), encoding="utf-8")
    pcm, cgm = make_checkouts()

    rc = installer.run(run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout()))
    out = capsys.readouterr().out
    assert rc == 1
    assert "state=CONFLICTED" in out
    assert "stack-manifest.json" in out
    assert "foreign content" in out
    # Nothing was written anywhere.
    assert not (adopter / ".coord").exists()
    assert json.loads((adopter / "stack-manifest.json").read_text(encoding="utf-8")) == foreign


def test_partial_reports_the_one_remaining_command(
    tmp_path, installer, make_acs_root, make_adopter, make_checkouts,
    stub_externals, run_args, capsys,
):
    """No --oio-root: coordination is installed and valid, OIO is the remaining step."""
    stub_externals()
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    rc = installer.run(run_args(make_acs_root(), adopter, pcm, cgm, None))
    out = capsys.readouterr().out
    assert rc == 1
    assert "PARTIAL (state=PARTIAL)" in out
    assert "OIO not installed" in out
    assert "observational-issue-ops" in out
    # The coordination surface is still written and honest about the state.
    lock = json.loads((adopter / ".coord" / "hotload.lock.json").read_text(encoding="utf-8"))
    assert lock["state"] == "PARTIAL"
    assert lock["oio_install"] == "not_run"


def test_unsupported_platform_reports_partial_never_ok(
    tmp_path, installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args, capsys,
):
    stub_externals(oio_supported=False)
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    rc = installer.run(run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout()))
    out = capsys.readouterr().out
    assert rc == 1
    assert "PARTIAL" in out
    assert "O_NOFOLLOW" in out
    lock = json.loads((adopter / ".coord" / "hotload.lock.json").read_text(encoding="utf-8"))
    assert lock["state"] == "PARTIAL"


def test_missing_cgm_adapter_fails_closed(
    tmp_path, installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args, capsys,
):
    stub_externals()
    adopter = make_adopter(with_adapter=False)
    pcm, cgm = make_checkouts()
    rc = installer.run(run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout()))
    out = capsys.readouterr().out
    assert rc == 1
    assert ".content-system" in out
    assert not (adopter / ".coord").exists()
    assert not (adopter / "stack-manifest.json").exists()


def test_missing_checkout_fails_closed(
    tmp_path, installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args, capsys,
):
    stub_externals()
    adopter = make_adopter()
    pcm, _ = make_checkouts()
    rc = installer.run(run_args(make_acs_root(), adopter, pcm, None, make_oio_checkout()))
    out = capsys.readouterr().out
    assert rc == 1
    assert "cgm" in out
    assert not (adopter / ".coord").exists()


def test_dry_run_reaches_the_plan_and_writes_nothing(
    tmp_path, installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args, capsys,
):
    stub_externals()
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    rc = installer.run(
        run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout(), dry_run=True)
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry-run OK" in out
    assert not (adopter / ".coord").exists()
    assert not (adopter / "stack-manifest.json").exists()
