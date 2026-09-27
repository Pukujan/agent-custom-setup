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


REQUIRED_CGM_MODULES = (
    "brand-foundation",
    "content-context",
    "writing-direction",
    "human-sounding-writing",
    "visual-direction",
    "image-generation",
    "html-demo",
)

REQUIRED_PCM_FEATURES = (
    "checkout_continuity_checkpoints",
    "github_issues_own_task_progression",
    "pr_only_to_default_branch",
    "required_ci_gates",
    "branch_protection_preference",
    "github_auto_merge_preference",
    "fail_closed_on_missing_gates",
    "leaf_parent_dependency_receipts",
)

CGM_PIN_VERSION = "0.5.1"
CGM_PIN_REVISION_PREFIX = "9874b26"
PCM_PIN_REVISION_PREFIX = "4e23854"


def validate_pins(data: object) -> list[str]:
    """Require FULL PCM + FULL CGM pins (Alex binding: no slim subsets)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["assignment must be an object"]
    pins = data.get("pins")
    if not isinstance(pins, dict):
        errors.append("pins: required object missing (FULL PCM + FULL CGM)")
        return errors

    pcm = pins.get("pcm")
    if not isinstance(pcm, dict):
        errors.append("pins.pcm: required (FULL PCM stack)")
    else:
        rev = str(pcm.get("revision") or "")
        if not rev.startswith(PCM_PIN_REVISION_PREFIX):
            errors.append(
                f"pins.pcm.revision: must pin FULL PCM at {PCM_PIN_REVISION_PREFIX}… "
                "(CLI 0.6.0); slim/unpinned PCM is incomplete"
            )
        feats = pcm.get("required_features")
        if not isinstance(feats, list):
            errors.append("pins.pcm.required_features: required list of FULL PCM features")
        else:
            missing = [f for f in REQUIRED_PCM_FEATURES if f not in feats]
            if missing:
                errors.append(
                    "pins.pcm.required_features: missing FULL PCM features: "
                    + ", ".join(missing)
                )

    cgm = pins.get("cgm")
    if not isinstance(cgm, dict):
        errors.append("pins.cgm: required (FULL CGM 0.5.1 stack)")
    else:
        ver = str(cgm.get("version") or "")
        if ver != CGM_PIN_VERSION:
            errors.append(
                f"pins.cgm.version: must be {CGM_PIN_VERSION} (FULL stack; not 0.5.0 HSW-only)"
            )
        rev = str(cgm.get("revision") or "")
        if not rev.startswith(CGM_PIN_REVISION_PREFIX):
            errors.append(
                f"pins.cgm.revision: must pin FULL CGM at {CGM_PIN_REVISION_PREFIX}… (0.5.1)"
            )
        mods = cgm.get("modules")
        if not isinstance(mods, list):
            errors.append("pins.cgm.modules: required list of all seven CGM module ids")
        else:
            # accept either bare ids or modules/<id> paths
            normalized = []
            for m in mods:
                s = str(m).strip().rstrip("/")
                if s.startswith("modules/"):
                    s = s[len("modules/") :]
                normalized.append(s)
            missing = [m for m in REQUIRED_CGM_MODULES if m not in normalized]
            if missing:
                errors.append(
                    "pins.cgm.modules: FULL CGM requires all seven modules; missing: "
                    + ", ".join(missing)
                )
            if len(normalized) < 7:
                errors.append(
                    "pins.cgm.modules: slim subset incomplete — need all seven CGM modules"
                )
        hoc = cgm.get("human_output_contract")
        if not isinstance(hoc, list) or len(hoc) < 5:
            errors.append(
                "pins.cgm.human_output_contract: required list (playbook/template/contract/"
                "quality/provenance/routing) — README contract is part of FULL CGM"
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
    errors.extend(validate_pins(data))
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
    print("  install_surface=FULL PCM + FULL CGM 0.5.1 + this runtime")
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
