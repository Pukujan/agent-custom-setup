#!/usr/bin/env python3
"""Install the multi-agent hotload coordination surface into a working repo.

Prepares and validates an adopter's local hotload install against this pack's
pinned external checkouts. This is **not** a network installer: it never clones,
never fetches, and never vendors PCM or CGM source. Bring checkouts at the
pinned commits (or point at ones you already have).

What it does, in order:

1. Checks the pack's own pins agree (runs ``check_pins.py`` on the ACS checkout).
2. Requires the adopter to already carry a CGM ``.content-system/`` adapter --
   authoring that adapter is CGM's job, not ACS's -- and verifies the pinned
   PCM/CGM checkouts sit at the exact pinned commits.
3. Writes the adopter's coordination surface, only when every precondition holds:

       .coord/assignment.json     pins declared from this pack's ``pins.json``
       .coord/hotload.lock.json   installed pack version + verified checkouts

   Existing files are kept unless ``--force``. ``--dry-run`` writes nothing.
4. Runs the pack's ``hotload_check.py`` against the adopter and fails closed.
5. Prints the GitHub governance steps a human must still take.

Out of scope by design (fails closed; never faked):

* Generating a CGM ``.content-system/`` adapter.
* Branch protection, required checks, auto-merge (human GitHub actions).

Usage:

    python scripts/acs_install.py \\
      --adopter-root /path/to/working-repo \\
      --pcm-root /path/to/project-continuity-modules \\
      --cgm-root /path/to/content-generation-modules
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
# v0.1.0 -> multi-agent-hotload -> coordination -> modules -> repo root
REPO_ROOT = MODULE_ROOT.parents[3]
DEFAULT_MANIFEST = MODULE_ROOT / "pins.json"
EXAMPLE_ASSIGNMENT = MODULE_ROOT / "examples" / "assignment.example.json"
HOTLOAD_CHECK = MODULE_ROOT / "scripts" / "hotload_check.py"
CHECK_PINS = MODULE_ROOT / "scripts" / "check_pins.py"

ADAPTER_REL = Path(".content-system")
COORD_REL = Path(".coord")
ASSIGNMENT_REL = COORD_REL / "assignment.json"
LOCK_REL = COORD_REL / "hotload.lock.json"
LOCK_SCHEMA = "acs.hotload.lock.v1"

# The claim file the generated assignment points at (self-contained; no foreign
# issue URL is baked into an adopter's assignment).
CLAIM_FILE_PATH = ".coord/boss_claim.json"


def console_safe(text: str) -> str:
    """ASCII-safe for Windows cp1252 consoles (unicode punctuation crashes print)."""
    return (
        text.replace("→", "->")
        .replace("←", "<-")
        .replace("⇒", "=>")
        .replace("—", "--")
        .replace("–", "-")
        .replace("…", "...")
        .replace(" ", " ")
    )


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def git_head(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip() or None


def short(value: str | None) -> str:
    if not value:
        return "(none)"
    return value[:7] + "..." if len(value) == 40 else value


def commits_agree(head: str, expected: str) -> bool:
    head, expected = head.lower(), expected.lower()
    return head == expected or head.startswith(expected) or expected.startswith(head)


def resolve_acs_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    return REPO_ROOT.resolve()


def verify_checkout(root: Path | None, expected_commit: str, label: str) -> list[str]:
    """Fail-closed check that ``root`` is a git checkout at the pinned commit."""
    if root is None:
        return [
            f"--{label}-root not provided: cannot verify the pinned {label.upper()} "
            f"checkout at {short(expected_commit)}"
        ]
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        return [f"{label}: checkout path is not a directory: {resolved}"]
    head = git_head(resolved)
    if not head:
        return [f"{label}: {resolved} is not a git checkout (rev-parse HEAD failed)"]
    if not commits_agree(head, expected_commit):
        return [
            f"{label}: HEAD {short(head)} must be pinned at {short(expected_commit)} "
            f"(wrong revision; do not follow moving main)"
        ]
    return []


def build_assignment(example: dict, pins: dict, project_name: str) -> dict:
    """Seed the adopter assignment from the pack example, re-pinned from pins.json."""
    data = copy.deepcopy(example)
    data["project"] = project_name
    data["recorded_at"] = now_iso()
    data["notes"] = (
        "Generated by acs_install.py from the pack's pins.json. Seed list is a hint; "
        "live join/continue order fills roles. Boss lease default 30 minutes (15-120); "
        "watchdog agent-less ~10m. After vacancy the claim_queue is FIFO; an old boss "
        "rejoins at the end. FULL PCM + FULL CGM required -- not a slim subset. "
        "EDIT the agents list and check_in to match your seats and issue. "
        "check_in.mechanism=claim_file writes local coordination state at "
        f"{CLAIM_FILE_PATH} only; it is NOT GitHub governance -- branch protection, "
        "required CI checks, and auto-merge stay human steps (see acs_install output)."
    )

    # Re-pin from the single source of truth (pins.json), never from the example.
    pcm_pin = pins["pcm"]
    cgm_pin = pins["cgm"]
    pcm_block = data.setdefault("pins", {}).setdefault("pcm", {})
    pcm_block["revision"] = pcm_pin["commit"]
    pcm_block["cli_version"] = pcm_pin["cli_version"]
    cgm_block = data["pins"].setdefault("cgm", {})
    cgm_block["revision"] = cgm_pin["commit"]
    cgm_block["version"] = cgm_pin["version"]
    cgm_block["modules"] = list(cgm_pin["modules"])

    # Self-contained check-in: never bake a foreign repo's issue URL into the adopter.
    bf = data.setdefault("boss_failover", {})
    check_in = bf.setdefault("check_in", {})
    check_in.pop("issue_url", None)
    check_in["mechanism"] = "claim_file"
    check_in["claim_file_path"] = CLAIM_FILE_PATH
    check_in.setdefault("interval_hint_minutes", 15)

    # Reset live coordination state to a clean seed.
    bf["claim_queue"] = []
    bf["standby"] = []
    bf["grace_minutes"] = bf.get("grace_minutes", 10)
    seed_boss = None
    agents = data.get("agents")
    if isinstance(agents, list) and agents and isinstance(agents[0], dict):
        seed_boss = agents[0].get("agent_id")
    bf["who_is_boss_now"] = seed_boss
    bf["as_of_history"] = (
        [
            {
                "as_of": now_iso(),
                "boss_agent_id": seed_boss,
                "ended_at": None,
                "notes": "Generated seed; append on failover -- never rewrite.",
            }
        ]
        if seed_boss
        else []
    )
    return data


def build_lock(pins: dict, acs_root: Path, checkouts: dict, validated: bool) -> dict:
    """Portable install record: no absolute local paths, safe to commit."""
    module_pin = pins.get("acs_hotload_module", {})
    return {
        "schema": LOCK_SCHEMA,
        "installed_at": now_iso(),
        "acs": {
            "module_id": module_pin.get("id"),
            "module_version": module_pin.get("version"),
            "commit": git_head(acs_root),
        },
        "pins": copy.deepcopy(pins),
        "checkouts": {
            "pcm": {
                "commit": checkouts.get("pcm", {}).get("commit"),
                "verified": bool(checkouts.get("pcm", {}).get("verified")),
            },
            "cgm": {
                "commit": checkouts.get("cgm", {}).get("commit"),
                "verified": bool(checkouts.get("cgm", {}).get("verified")),
            },
        },
        "hotload_check": "OK" if validated else "not_run",
    }


def write_json_atomic(path: Path, data: object, *, root: Path) -> None:
    """Write JSON via a temp file in the same dir, then replace (no partial file).

    Refuses to write outside ``root`` so a symlinked ``.coord`` (or any other
    redirect) cannot be used to escape the adopter tree under ``--force``.
    """
    root_r = root.resolve()
    parent_r = path.parent.resolve()
    if parent_r != root_r and root_r not in parent_r.parents:
        raise ValueError(f"refusing to write outside adopter root: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        target_r = path.resolve()
        if target_r != root_r and root_r not in target_r.parents:
            raise ValueError(f"refusing to write outside adopter root: {path}")
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def run_script(argv: list[str]) -> int:
    try:
        return subprocess.run(argv, check=False).returncode
    except OSError as exc:
        print(f"acs_install: could not run {argv[0]}: {exc}")
        return 1


def run(args: argparse.Namespace) -> int:
    acs_root = resolve_acs_root(args.acs_root)
    manifest_path = acs_root / DEFAULT_MANIFEST.relative_to(REPO_ROOT)
    try:
        manifest = load_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"acs_install: FAIL\n  - pins manifest unreadable: {manifest_path}: {exc}")
        return 2
    if not isinstance(manifest, dict) or not isinstance(manifest.get("pins"), dict):
        print(f"acs_install: FAIL\n  - {manifest_path} has no 'pins' object")
        return 2
    pins = manifest["pins"]

    problems: list[str] = []

    # 1. The pack's own projections must agree before we touch anything.
    if run_script(
        [sys.executable, str(CHECK_PINS), "--root", str(acs_root)]
    ) != 0:
        problems.append(
            "pack pin drift: check_pins.py failed on the ACS checkout "
            f"({acs_root}); fix the pack before installing"
        )

    # 2. Adopter root must exist.
    adopter = args.adopter_root.expanduser().resolve()
    if not adopter.is_dir():
        print(f"acs_install: FAIL\n  - adopter root is not a directory: {adopter}")
        return 2

    # 3. A CGM adapter must already exist -- ACS does not author one.
    adapter = adopter / ADAPTER_REL
    if not adapter.is_dir():
        problems.append(
            f"adopter has no CGM adapter at {adapter} -- author the .content-system "
            "adapter first (CGM's job, not ACS's), then re-run; a partial install "
            "never looks complete"
        )

    # 4. Verify the pinned external checkouts.
    checkouts: dict[str, dict] = {}
    for label, root_arg, expected in (
        ("pcm", args.pcm_root, pins.get("pcm", {}).get("commit", "")),
        ("cgm", args.cgm_root, pins.get("cgm", {}).get("commit", "")),
    ):
        errs = verify_checkout(root_arg, expected, label)
        problems.extend(errs)
        checkouts[label] = {
            "commit": git_head(root_arg.expanduser().resolve()) if root_arg else None,
            "verified": not errs,
        }

    # 5. Build the coordination surface; keep existing files unless --force.
    try:
        example = load_json(EXAMPLE_ASSIGNMENT)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"acs_install: FAIL\n  - assignment example unreadable: {exc}")
        return 2
    project_name = args.project_name or adopter.name
    targets: list[tuple[Path, object]] = [
        (adopter / ASSIGNMENT_REL, build_assignment(example, pins, project_name)),
        (adopter / LOCK_REL, build_lock(pins, acs_root, checkouts, validated=False)),
    ]
    to_write: list[tuple[Path, object]] = []
    kept: list[Path] = []
    for path, data in targets:
        if path.exists() and not args.force:
            kept.append(path)
        else:
            to_write.append((path, data))

    # 6. Report the plan.
    print("acs_install: plan")
    print(f"  acs_root={acs_root}")
    print(f"  adopter_root={adopter}")
    print(f"  pcm_pin={short(pins.get('pcm', {}).get('commit'))}  cgm_pin={short(pins.get('cgm', {}).get('commit'))}")
    for path, _ in to_write:
        print(f"  write {path.relative_to(adopter)}")
    for path in kept:
        print(f"  keep  {path.relative_to(adopter)} (exists; --force to overwrite)")

    if problems:
        print("acs_install: FAIL (preconditions unmet; nothing written)")
        for item in problems:
            for line in str(item).splitlines() or [str(item)]:
                print(f"  - {console_safe(line)}")
        return 1

    if args.dry_run:
        print("acs_install: dry-run OK (no files written)")
        return 0

    # 7. Write, then validate the whole stack with the pack's own checker.
    for path, data in to_write:
        try:
            write_json_atomic(path, data, root=adopter)
        except ValueError as exc:
            print(f"acs_install: FAIL\n  - {console_safe(str(exc))}")
            return 1

    check_argv = [
        sys.executable,
        str(HOTLOAD_CHECK),
        "--root",
        str(acs_root / MODULE_ROOT.relative_to(REPO_ROOT)),
        "--adopter-root",
        str(adopter),
        "--assignment",
        str(adopter / ASSIGNMENT_REL),
    ]
    if args.cgm_root:
        check_argv += ["--cgm-root", str(args.cgm_root.expanduser().resolve())]
    if run_script(check_argv) != 0:
        print("acs_install: FAIL (hotload_check did not pass; see above)")
        return 1

    # 8. Refresh the lock now that validation passed.
    write_json_atomic(
        adopter / LOCK_REL,
        build_lock(pins, acs_root, checkouts, validated=True),
        root=adopter,
    )

    print("acs_install: OK")
    print(f"  wrote {ASSIGNMENT_REL.as_posix()} and {LOCK_REL.as_posix()}")
    print("  next: EDIT the assignment's agents list + check_in to match your seats/issue.")
    print("  next (human GitHub steps, NOT automated): enable branch protection on the")
    print("  default branch with the required CI checks, and turn on auto-merge so green")
    print("  required checks can merge without skipping gates.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--adopter-root", type=Path, required=True)
    parser.add_argument("--acs-root", type=Path, default=None)
    parser.add_argument("--pcm-root", type=Path, default=None)
    parser.add_argument("--cgm-root", type=Path, default=None)
    parser.add_argument("--project-name", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Show the plan; write nothing.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated files.")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
