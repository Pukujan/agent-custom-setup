#!/usr/bin/env python3
"""Validate multi-agent hotload pack: required files + assignment schema + failover/watchdog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore

MODULE_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "README.md",
    "ROLES.md",
    "PROPOSALS.md",
    "HOTLOAD.md",
    "BEHAVIOR.md",
    "NOTES.md",
    "module.json",
    "schema/assignment.schema.json",
    "examples/assignment.example.json",
    "scripts/hotload_check.py",
    "scripts/watchdog_check.py",
    "workflow-stubs/watchdog.yml",
)


def check_required_files(root: Path) -> list[str]:
    return [rel for rel in REQUIRED_FILES if not (root / rel).is_file()]


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def validate_failover_watchdog(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["assignment must be an object"]
    bf = data.get("boss_failover")
    ttl = None
    if not isinstance(bf, dict):
        errors.append("boss_failover: required object missing")
    else:
        ttl = bf.get("lease_ttl_minutes")
        if not isinstance(ttl, (int, float)) or ttl < 15 or ttl > 120:
            errors.append(
                "boss_failover.lease_ttl_minutes: must be a number in 15..120 "
                "(default 30; short leases OK)"
            )
        if "lease_ttl_hours" in bf:
            errors.append(
                "boss_failover.lease_ttl_hours: removed — use lease_ttl_minutes "
                "(default 30; range 15–120)"
            )
        check_in = bf.get("check_in")
        if not isinstance(check_in, dict) or "mechanism" not in check_in:
            errors.append("boss_failover.check_in.mechanism: required")
        elif check_in.get("mechanism") not in ("issue_comment", "claim_file"):
            errors.append("boss_failover.check_in.mechanism: must be issue_comment or claim_file")
        if "standby" in bf and not isinstance(bf.get("standby"), list):
            errors.append("boss_failover.standby: must be an array when present")
        if "claim_queue" in bf and not isinstance(bf.get("claim_queue"), list):
            errors.append("boss_failover.claim_queue: must be an array when present (FIFO)")
        elif isinstance(bf.get("claim_queue"), list):
            for i, item in enumerate(bf["claim_queue"]):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"boss_failover.claim_queue[{i}]: must be non-empty string agent_id")
    wd = data.get("watchdog")
    if not isinstance(wd, dict):
        errors.append("watchdog: required object missing (agent-less liveness)")
    else:
        interval = wd.get("watchdog_interval_minutes")
        if not isinstance(interval, (int, float)) or interval < 5 or interval > 30:
            errors.append("watchdog.watchdog_interval_minutes: must be 5..30 (~10m typical)")
        idle = wd.get("idle_window")
        if not isinstance(idle, dict) or not isinstance(idle.get("minutes"), (int, float)):
            errors.append("watchdog.idle_window.minutes: required number")
        runner = wd.get("runner")
        if runner not in ("cron", "github_action", "script"):
            errors.append("watchdog.runner: must be cron|github_action|script (agent-less; no LLM)")
        if isinstance(ttl, (int, float)) and isinstance(interval, (int, float)):
            if interval >= ttl:
                errors.append(
                    "watchdog.watchdog_interval_minutes must stay below lease_ttl_minutes "
                    "(watchdog != failover; ~10m liveness only)"
                )
    return errors


def validate_assignment(schema_path: Path, assignment_path: Path) -> list[str]:
    errors: list[str] = []
    schema = load_json(schema_path)
    data = load_json(assignment_path)
    if jsonschema is None:
        errors.append("jsonschema is not installed; pip install jsonschema")
        return errors
    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in err.path) or "<root>"
        errors.append(f"{loc}: {err.message}")
    errors.extend(validate_failover_watchdog(data))
    return errors


def run(root: Path, assignment: Path | None = None) -> int:
    problems: list[str] = []
    missing = check_required_files(root)
    if missing:
        problems.extend(f"missing file: {m}" for m in missing)
    schema_path = root / "schema" / "assignment.schema.json"
    example_path = assignment or (root / "examples" / "assignment.example.json")
    if schema_path.is_file() and example_path.is_file():
        problems.extend(validate_assignment(schema_path, example_path))
    elif not example_path.is_file():
        problems.append(f"assignment not found: {example_path}")
    if problems:
        print("hotload_check: FAIL")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("hotload_check: OK")
    print(f"  module_root={root}")
    print(f"  assignment={example_path}")
    print("  install_surface=PCM + CGM + this runtime")
    print("  watchdog=agent-less ~10m; lease_ttl=minutes (default 30)")
    print("  claim_queue=FIFO after vacancy; zombie re-reads GitHub claim")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=MODULE_ROOT)
    parser.add_argument("--assignment", type=Path, default=None)
    args = parser.parse_args(argv)
    return run(args.root.resolve(), args.assignment)


if __name__ == "__main__":
    sys.exit(main())
