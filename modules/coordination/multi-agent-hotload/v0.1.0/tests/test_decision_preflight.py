"""ACS only checks task binding and propagates PCM live preflight; it cannot judge truth."""
from __future__ import annotations

import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "decision_preflight.py"


def _load():
    spec = spec_from_file_location("acs_decision_preflight", SCRIPT)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _expectation(tmp_path):
    path = tmp_path / "task-decision.json"
    path.write_text(json.dumps({
        "schema": "pcm.decision-precondition.v1",
        "repository": "Pukujan/agent-custom-setup",
        "issue_number": 85,
        "task_id": "ACS-0015",
        "expected_issue_state": "open",
        "expected_issue_updated_at": "2026-10-08T11:00:00Z",
    }), encoding="utf-8")
    return path


def _pcm_result(status: str, code: int) -> SimpleNamespace:
    return SimpleNamespace(
        returncode=code, stderr="",
        stdout=json.dumps({
            "schema": "pcm.decision-preflight-result.v1",
            "status": status,
            "reason": "test fixture",
            "task_id": "ACS-0015",
            "repository": "Pukujan/agent-custom-setup",
            "issue_number": 85,
            "expected_revision": "2026-10-08T11:00:00Z",
            "observed_revision": "2026-10-08T11:00:00Z",
        })
    )


def test_matching_live_pcm_result_is_current(tmp_path):
    mod = _load()
    record = _expectation(tmp_path)
    calls = []

    def runner(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return _pcm_result("CURRENT", 0)

    result = mod.preflight(record, "ACS-0015", "Pukujan/agent-custom-setup", runner=runner)
    assert result["status"] == "CURRENT"
    assert calls[0][0] == [sys.executable, "-m", "continuity.decision_preflight", "--expect", str(record)]
    assert calls[0][1]["timeout"] == 40


def test_stale_issue_is_not_admitted(tmp_path):
    mod = _load()
    result = mod.preflight(_expectation(tmp_path), "ACS-0015", "Pukujan/agent-custom-setup",
                           runner=lambda *a, **k: _pcm_result("STALE", 2))
    assert result["status"] == "STALE"


def test_new_issue_revision_requires_review(tmp_path):
    mod = _load()
    result = mod.preflight(_expectation(tmp_path), "ACS-0015", "Pukujan/agent-custom-setup",
                           runner=lambda *a, **k: _pcm_result("REVIEW_REQUIRED", 2))
    assert result["status"] == "REVIEW_REQUIRED"


def test_unavailable_pcm_module_fails_closed(tmp_path):
    mod = _load()
    result = mod.preflight(
        _expectation(tmp_path), "ACS-0015", "Pukujan/agent-custom-setup",
        runner=lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="No module")
    )
    assert result["status"] == "UNKNOWN"


def test_current_requires_expected_revision_proof(tmp_path):
    mod = _load()
    record = _expectation(tmp_path)
    for field in ("expected_revision", "observed_revision"):
        result = _pcm_result("CURRENT", 0)
        data = json.loads(result.stdout)
        data[field] = "2026-10-08T11:00:01Z"
        result.stdout = json.dumps(data)
        output = mod.preflight(record, "ACS-0015", "Pukujan/agent-custom-setup",
                               runner=lambda *a, **kw: result)
        assert output["status"] == "UNKNOWN"


def test_task_or_repository_mismatch_rejects_before_invocation(tmp_path):
    mod = _load()
    record = _expectation(tmp_path)
    def fail_runner(*a, **k):
        raise AssertionError("must not call PCM")
    assert mod.preflight(record, "ACS-0001", "Pukujan/agent-custom-setup", runner=fail_runner)["status"] == "UNKNOWN"
    assert mod.preflight(record, "ACS-0015", "Pukujan/unrelated", runner=fail_runner)["status"] == "UNKNOWN"


def test_timeout_fails_closed(tmp_path):
    mod = _load()
    def runner(*a, **k):
        raise subprocess.TimeoutExpired(cmd=["python"], timeout=40)
    assert mod.preflight(_expectation(tmp_path), "ACS-0015", "Pukujan/agent-custom-setup",
                         runner=runner)["status"] == "UNKNOWN"


def test_unparseable_or_spoofed_success_is_not_current(tmp_path):
    mod = _load()
    record = _expectation(tmp_path)
    for response in [
        SimpleNamespace(returncode=0, stdout="CURRENT", stderr=""),
        SimpleNamespace(returncode=0, stdout="{}", stderr=""),
        _pcm_result("CURRENT", 2),
    ]:
        result = mod.preflight(record, "ACS-0015", "Pukujan/agent-custom-setup",
                               runner=lambda *a, **k: response)
        assert result["status"] == "UNKNOWN"


def test_cli_maps_pcm_statuses_to_fail_closed_exit_codes(tmp_path, capsys):
    mod = _load()
    record = _expectation(tmp_path)
    for state, expected in [("CURRENT", 0), ("STALE", 2), ("REVIEW_REQUIRED", 2), ("UNKNOWN", 3)]:
        with patch.object(mod, "preflight", return_value={"status": state, "reason": "fixture"}):
            code = mod.main(["--expect", str(record), "--task", "ACS-0015",
                             "--repo", "Pukujan/agent-custom-setup"])
        assert code == expected
        assert state in capsys.readouterr().out
