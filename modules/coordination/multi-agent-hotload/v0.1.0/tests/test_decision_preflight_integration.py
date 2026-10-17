"""Exercise ACS -> PCM subprocess boundary and an opt-in guarded action.

The fake PCM module replaces remote reads, not the ACS adapter. This does
not claim the existing ACS claim queue automatically invokes this guard.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "decision_preflight.py"


@pytest.fixture()
def isolated_pcm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = tmp_path / "continuity"
    module.mkdir()
    (module / "__init__.py").write_text("", encoding="utf-8")
    (module / "decision_preflight.py").write_text(
        """import json, os, sys
from pathlib import Path
record = json.loads(Path(sys.argv[sys.argv.index("--expect")+1]).read_text())
status = os.environ["PCM_TEST_STATUS"]
code = 0 if status == "CURRENT" else (2 if status != "UNKNOWN" else 3)
out = {
    "schema": "pcm.decision-preflight-result.v1",
    "status": status,
    "reason": "isolated integration fixture",
    "repository": record["repository"],
    "issue_number": record["issue_number"],
    "task_id": record["task_id"],
    "expected_revision": record["expected_issue_updated_at"],
    "observed_revision": record["expected_issue_updated_at"] if status == "CURRENT" else None,
}
print(json.dumps(out))
sys.exit(code)
""",
        encoding="utf-8",
    )
    expected = tmp_path / "expected.json"
    expected.write_text(
        json.dumps({
            "schema": "pcm.decision-precondition.v1",
            "repository": "Pukujan/agent-custom-setup",
            "issue_number": 85,
            "task_id": "ACS-0015",
            "expected_issue_state": "open",
            "expected_issue_updated_at": "2026-10-08T11:00:00Z",
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    return expected


@pytest.mark.parametrize(
    ("state", "expected_code", "action_must_run"),
    [
        ("CURRENT", 0, True),
        ("STALE", 2, False),
        ("REVIEW_REQUIRED", 2, False),
        ("UNKNOWN", 3, False),
    ],
)
def test_guarded_action_runs_only_after_current(
    isolated_pcm: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    state: str, expected_code: int, action_must_run: bool,
):
    monkeypatch.setenv("PCM_TEST_STATUS", state)
    command = [
        sys.executable, str(SCRIPT), "--expect", str(isolated_pcm),
        "--task", "ACS-0015", "--repo", "Pukujan/agent-custom-setup",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == expected_code
    assert json.loads(result.stdout)["status"] == state

    sentinel = tmp_path / "expensive-action-did-run.txt"
    if result.returncode == 0:
        # Simulate guarded workflow with no shell or quoting assumptions.
        subprocess.run(
            [sys.executable, "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('ran')",
             str(sentinel)],
            check=True,
        )
    assert sentinel.exists() is action_must_run


def test_missing_pcm_dependency_blocks_guarded_action(
    isolated_pcm: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    empty_package = tmp_path / "no-pcm-installed" / "continuity"
    empty_package.mkdir(parents=True)
    (empty_package / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(empty_package.parent))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--expect", str(isolated_pcm),
         "--task", "ACS-0015", "--repo", "Pukujan/agent-custom-setup"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 3
    assert json.loads(result.stdout)["status"] == "UNKNOWN"
