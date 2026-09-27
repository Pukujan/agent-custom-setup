#!/usr/bin/env python3
"""Validate multi-agent hotload pack: files, pins, FULL CGM validate_content_system, failover."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
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
CGM_PIN_REVISION = "9874b26dc46499137bf22e1ca163874ef2dd5e7a"
CGM_HELPER_REPO = "https://github.com/Pukujan/content-generation-modules"


def discover_cgm_root(explicit: Path | None = None) -> Path | None:
    """Resolve CGM checkout: --cgm-root, CGM_ROOT, then common sibling/local paths."""
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    env = os.environ.get("CGM_ROOT")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve()
    # ACS repo root = parents[4] from scripts/ under v0.1.0 pack
    acs_root = MODULE_ROOT.parents[3]  # v0.1.0 → multi-agent-hotload → coordination → modules → repo
    candidates.extend(
        [
            Path("/workspace/cgm-051"),
            Path("/workspace/cgm-hsw"),
            acs_root.parent / "content-generation-modules",
            Path.home() / "content-generation-modules",
            Path("D:/claude/content-generation-modules"),
            Path("C:/Users/pujan/content-generation-modules"),
        ]
    )
    for cand in candidates:
        try:
            root = cand.expanduser().resolve()
        except OSError:
            continue
        marker = root / "scripts" / "validate_content_system.py"
        version = root / "system-version.json"
        if marker.is_file() and version.is_file():
            return root
    return None


def discover_adopter_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    env = os.environ.get("ADOPTER_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # Default: ACS repository root containing this pack
    return MODULE_ROOT.parents[3].resolve()


def cgm_checkout_sha(cgm_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cgm_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip()


def validate_cgm_live(
    cgm_root: Path | None,
    adopter_root: Path,
    *,
    require: bool = True,
) -> list[str]:
    """Fail install unless CGM pin SHA is checked out and validate_content_system prints VALID."""
    errors: list[str] = []
    if cgm_root is None:
        if require:
            errors.append(
                "CGM checkout not found: set CGM_ROOT or pass --cgm-root to a "
                f"content-generation-modules tree pinned at {CGM_PIN_REVISION} (0.5.1)"
            )
        return errors

    sha = cgm_checkout_sha(cgm_root)
    if not sha:
        errors.append(f"CGM_ROOT={cgm_root} is not a git checkout (rev-parse HEAD failed)")
        return errors
    if not (
        sha.startswith(CGM_PIN_REVISION_PREFIX)
        or sha.lower() == CGM_PIN_REVISION.lower()
        or CGM_PIN_REVISION.lower().startswith(sha.lower()[:12])
    ):
        # Accept exact full SHA match or prefix match on pinned commit
        if sha.lower() != CGM_PIN_REVISION.lower() and not sha.lower().startswith(
            CGM_PIN_REVISION_PREFIX.lower()
        ):
            errors.append(
                f"CGM checkout HEAD={sha} must be pinned at {CGM_PIN_REVISION} "
                f"(helper_version {CGM_PIN_VERSION}); got wrong revision"
            )
            return errors

    # Confirm helper system-version.json reports 0.5.1 + seven modules
    try:
        version = load_json(cgm_root / "system-version.json")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"CGM system-version.json unreadable: {exc}")
        return errors
    if not isinstance(version, dict) or str(version.get("version")) != CGM_PIN_VERSION:
        errors.append(
            f"CGM system-version.json version must be {CGM_PIN_VERSION} at pin "
            f"{CGM_PIN_REVISION}"
        )
    mods = version.get("modules") if isinstance(version, dict) else None
    if not isinstance(mods, list) or set(mods) != set(REQUIRED_CGM_MODULES):
        errors.append(
            "CGM system-version.json modules must be exactly the seven FULL modules "
            "(slim HSW+WD-only fails)"
        )

    adapter = adopter_root / ".content-system"
    if not adapter.is_dir():
        errors.append(
            f"adopter missing .content-system adapter at {adapter} "
            "(FULL CGM install requires target adapter)"
        )
        return errors

    script = cgm_root / "scripts" / "validate_content_system.py"
    if not script.is_file():
        errors.append(f"missing {script}")
        return errors

    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--root",
                str(cgm_root),
                "--adapter",
                str(adapter),
                "--project-root",
                str(adopter_root),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        errors.append(f"failed to run validate_content_system.py: {exc}")
        return errors

    out = (proc.stdout or "") + (proc.stderr or "")
    first = next((ln.strip() for ln in out.splitlines() if ln.strip()), "")
    if proc.returncode != 0 or not first.startswith("VALID"):
        detail = f"(exit={proc.returncode}, first_line={first!r}). Output:\n{out.strip()}"
        errors.append("validate_content_system.py did not return VALID " + detail)
    return errors




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


def run(
    root: Path,
    assignment: Path | None = None,
    *,
    cgm_root: Path | None = None,
    adopter_root: Path | None = None,
    skip_cgm_validate: bool = False,
) -> int:
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

    resolved_adopter = discover_adopter_root(adopter_root)
    resolved_cgm = discover_cgm_root(cgm_root)
    if skip_cgm_validate:
        # Explicit opt-out for isolated schema unit tests only — not a successful install.
        print("hotload_check: WARN skip_cgm_validate=1 (schema-only; install incomplete)")
    else:
        problems.extend(
            validate_cgm_live(resolved_cgm, resolved_adopter, require=True)
        )

    if problems:
        print("hotload_check: FAIL")
        for item in problems:
            for line in str(item).splitlines() or [str(item)]:
                print(f"  - {line}")
        return 1
    print("hotload_check: OK")
    print(f"  module_root={root}")
    print(f"  assignment={example_path}")
    print(f"  cgm_root={resolved_cgm}")
    print(f"  adopter_root={resolved_adopter}")
    print(f"  cgm_pin={CGM_PIN_VERSION}@{CGM_PIN_REVISION}")
    print("  install_surface=FULL PCM + FULL CGM 0.5.1 + this runtime")
    print("  cgm_validate=VALID (validate_content_system.py)")
    print("  watchdog=agent-less ~10m; lease_ttl=minutes (default 30)")
    print("  claim_queue=FIFO after vacancy; zombie re-reads GitHub claim")
    print(
        "  next: load CGM modules per docs/WRITING_ROUTING.md "
        "(README/product → writing-direction; posts/prose → hsw). "
        "Titles/bodies remain agent discipline — validate does not score prose."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=MODULE_ROOT)
    parser.add_argument("--assignment", type=Path, default=None)
    parser.add_argument(
        "--cgm-root",
        type=Path,
        default=None,
        help="Path to content-generation-modules checkout (else CGM_ROOT / discovery)",
    )
    parser.add_argument(
        "--adopter-root",
        type=Path,
        default=None,
        help="Adopter repo root with .content-system (else ADOPTER_ROOT / ACS root)",
    )
    parser.add_argument(
        "--skip-cgm-validate",
        action="store_true",
        help="Schema-only (tests). A real install must NOT use this flag.",
    )
    args = parser.parse_args(argv)
    skip = bool(args.skip_cgm_validate) or os.environ.get("HOTLOAD_SKIP_CGM_VALIDATE") == "1"
    return run(
        args.root.resolve(),
        args.assignment,
        cgm_root=args.cgm_root,
        adopter_root=args.adopter_root,
        skip_cgm_validate=skip,
    )


if __name__ == "__main__":
    sys.exit(main())
