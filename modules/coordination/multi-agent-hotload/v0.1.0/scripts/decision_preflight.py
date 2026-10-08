#!/usr/bin/env python3
"""ACS read-only adapter for PCM's explicit live issue decision preconditions.

Opt-in until the train pins a PCM release that carries this module.
A role/lease or a successful invocation alone is not owner authorization.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_CURRENT = 0
EXIT_REVIEW = 2
EXIT_UNKNOWN = 3


def preflight(expectation: Path, task_id: str, repository: str,
              *, runner: Any = subprocess.run) -> dict[str, Any]:
    """Only PCM decides issue-revision freshness; ACS checks task binding."""
    try:
        record = json.loads(expectation.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "UNKNOWN", "reason": "Cannot read precondition JSON"}
    if not isinstance(record, dict):
        return {"status": "UNKNOWN", "reason": "Precondition is not an object"}
    if record.get("schema") != "pcm.decision-precondition.v1":
        return {"status": "UNKNOWN", "reason": "Unrecognized PCM precondition schema"}
    if record.get("task_id") != task_id or record.get("repository") != repository:
        return {"status": "UNKNOWN", "reason": "Precondition belongs to a different task or repository"}
    cmd = [sys.executable, "-m", "continuity.decision_preflight", "--expect", str(expectation)]
    try:
        proc = runner(cmd, capture_output=True, text=True, timeout=40, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "UNKNOWN", "reason": "PCM live preflight unavailable"}
    if proc.returncode not in (EXIT_CURRENT, EXIT_REVIEW, EXIT_UNKNOWN):
        return {"status": "UNKNOWN", "reason": "PCM preflight missing or returned an unsupported result"}
    try:
        result = json.loads(proc.stdout)
    except (ValueError, TypeError):
        return {"status": "UNKNOWN", "reason": "PCM preflight returned no parseable result"}
    if not isinstance(result, dict):
        return {"status": "UNKNOWN", "reason": "PCM preflight response is not an object"}
    status = result.get("status")
    if (result.get("schema") != "pcm.decision-preflight-result.v1"
            or result.get("task_id") != task_id
            or result.get("repository") != repository
            or result.get("issue_number") != record.get("issue_number")
            or (status == "CURRENT" and result.get("expected_revision") != record.get("expected_issue_updated_at"))
            or (status == "CURRENT" and result.get("observed_revision") != record.get("expected_issue_updated_at"))
            or (status == "CURRENT" and proc.returncode != EXIT_CURRENT)
            or (status in ("STALE", "REVIEW_REQUIRED") and proc.returncode != EXIT_REVIEW)
            or (status == "UNKNOWN" and proc.returncode != EXIT_UNKNOWN)
            or status not in ("CURRENT", "STALE", "REVIEW_REQUIRED", "UNKNOWN")):
        return {"status": "UNKNOWN", "reason": "PCM result identity or exit code mismatch"}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACS task-boundary PCM decision preflight (read-only)")
    parser.add_argument("--expect", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--repo", required=True, help="Owning repo in OWNER/REPO form")
    args = parser.parse_args(argv)
    result = preflight(args.expect, args.task, args.repo)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    if result["status"] == "CURRENT":
        return EXIT_CURRENT
    return EXIT_REVIEW if result["status"] in ("STALE", "REVIEW_REQUIRED") else EXIT_UNKNOWN


if __name__ == "__main__":
    raise SystemExit(main())
