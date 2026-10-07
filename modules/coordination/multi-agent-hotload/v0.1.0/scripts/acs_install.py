#!/usr/bin/env python3
"""Install the multi-agent hotload coordination surface into a working repo.

Prepares and validates an adopter's local hotload install against this pack's
pinned external checkouts. This is **not** a network installer: it never clones,
never fetches, and never vendors PCM or CGM source. Bring checkouts at the
pinned commits (or point at ones you already have).

Prerequisites (the installer fails closed without all of them):

* the adopter already carries a CGM ``.content-system/`` adapter -- authoring
  that adapter is CGM's job, not ACS's;
* a PCM checkout at the mesh commit;
* a CGM checkout at the mesh commit;
* Python deps the validators need (``jsonschema``).

``--oio-root`` points at an observational-issue-ops checkout at the mesh commit.
Without it (or where the pinned OIO installer reports it cannot run here) the
install is **PARTIAL**: the coordination surface is written and valid, OIO is
reported as the one remaining step, and the exit code is non-zero -- never a
fake success. Whether OIO can run is asked of the pinned installer
(``--check-platform``), not decided here, so this installer cannot go stale
against OIO's own platform support.

What it does, in order:

1. Checks the pack's own pins agree (runs ``check_pins.py`` on the ACS checkout).
2. Verifies the PCM/CGM/OIO checkouts sit at the commits in ``stack-mesh.json``.
   An older commit is refused.
3. Builds the adopter's coordination surface:

       .coord/assignment.json     pins declared from this pack's ``pins.json``
       .coord/hotload.lock.json   installed pack version + verified checkouts + state
       stack-manifest.json        empty pins -- the adopter follows the train

4. Writes them atomically, keeping existing files unless ``--force``, refusing to
   write outside the adopter root, and refusing to overwrite a hand-written
   ``stack-manifest.json``. ``--dry-run`` writes nothing.
5. Runs the pack's ``hotload_check.py`` (which validates the adopter's adapter);
   on failure the writes are rolled back.
6. Invokes the pinned OIO installer to add the issue-log surface, then its
   ``--check``. OIO is transactional on its own; a failure leaves the PARTIAL
   state above rather than rolling back the validated coordination surface.
7. Prints the GitHub governance steps a human must still take.

Only each checkout's HEAD commit is verified; a dirty working tree is not
detected (this matches ``hotload_check.py``).

Out of scope by design (fails closed; never faked):

* Generating a CGM ``.content-system/`` adapter.
* Porting OIO's installer to Windows (tracked in the OIO issue log).
* Branch protection, required checks, auto-merge (human GitHub actions).

Usage:

    python scripts/acs_install.py \\
      --adopter-root /path/to/working-repo \\
      --pcm-root /path/to/project-continuity-modules \\
      --cgm-root /path/to/content-generation-modules \\
      --oio-root /path/to/observational-issue-ops
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

MANIFEST_REL = Path("stack-manifest.json")
MANIFEST_SCHEMA = "agent-stack-train.stack-manifest.v1"
# The train's stable name (stack-releases.json "release_train"). A name, not a
# version pin; tests/test_train_parity.py checks it against the live train.
TRAIN_RELEASE = "current"
OIO_COMPONENT = "observational-issue-ops"
OIO_INSTALLER_REL = Path(".github") / "scripts" / "oio_installer.py"
OIO_MANIFEST_REL = Path(".oio") / "install-manifest.json"
OIO_JOURNAL_REL = Path(".oio") / ".installer-transaction.json"

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


def say(text: object = "") -> None:
    print(console_safe(str(text)))


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
            f"{label}: HEAD {short(head)} must be {short(expected_commit)} "
            f"(an older version is refused)"
        ]
    return []


def build_assignment(example: dict, pins: dict, project_name: str) -> dict:
    """Seed the adopter assignment from the pack example, re-pinned from pins.json.

    Every pin-bearing field is rebuilt from ``pins.json`` so no stale value from
    the example can survive a pin bump.
    """
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

    pcm_pin = pins["pcm"]
    cgm_pin = pins["cgm"]
    pin_block = data.setdefault("pins", {})
    pcm_block = pin_block.setdefault("pcm", {})
    pcm_block["revision"] = pcm_pin["commit"]
    pcm_block["cli_version"] = pcm_pin["cli_version"]
    pcm_block["notes"] = (
        "Full PCM for adopters: continuity/checkpoints plus PR-only, required CI "
        "gates, protection/auto-merge preference, fail-closed gates, leaf/parent "
        "receipts. The commit comes from stack-mesh.json. An older checkout is "
        "refused. Do not vendor PCM source."
    )
    cgm_block = pin_block.setdefault("cgm", {})
    cgm_block["revision"] = cgm_pin["commit"]
    cgm_block["version"] = cgm_pin["version"]
    cgm_block["modules"] = list(cgm_pin["modules"])
    cgm_block["notes"] = (
        "FULL CGM required for ACS and every hotloader adopter: all eight modules "
        "including human-output-naming. The commit comes from stack-mesh.json. "
        "An older checkout is refused. Validate with CGM's "
        "validate_content_system.py; then apply acs_prompt_inject. Do not vendor "
        "CGM source."
    )

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


def build_lock(
    pins: dict,
    acs_root: Path,
    checkouts: dict,
    validated: bool,
    *,
    state: str = "ABSENT",
    oio_install: str = "not_run",
) -> dict:
    """Portable install record: no absolute local paths, safe to commit."""
    module_pin = pins.get("acs_hotload_module", {})
    recorded = {
        label: {
            "commit": (checkouts.get(label) or {}).get("commit"),
            "verified": bool((checkouts.get(label) or {}).get("verified")),
        }
        for label in ("pcm", "cgm", "oio")
    }
    return {
        "schema": LOCK_SCHEMA,
        "installed_at": now_iso(),
        "state": state,
        "acs": {
            "module_id": module_pin.get("id"),
            "module_version": module_pin.get("version"),
            "commit": git_head(acs_root),
        },
        "pins": copy.deepcopy(pins),
        "stack_manifest": MANIFEST_REL.as_posix(),
        "checkouts": recorded,
        "oio_install": oio_install,
        "hotload_check": "OK" if validated else "not_run",
    }


def build_stack_manifest(mesh_doc: dict, project_name: str) -> dict:
    """The adopter's ``stack-manifest.json``: pin every mesh component, but empty.

    An empty pin follows the train (agent-stack-train ``check_manifest.py``), so
    the adopter is never frozen to install-day versions.
    """
    requires = mesh_doc.get("requires") if isinstance(mesh_doc, dict) else None
    if not isinstance(requires, dict) or not requires:
        raise ValueError("stack-mesh.json has no 'requires' object")
    return {
        "schema_version": MANIFEST_SCHEMA,
        "adopter": project_name,
        "release_train": TRAIN_RELEASE,
        "source": mesh_doc.get("source", ""),
        "pins": {name: {} for name in sorted(requires)},
    }


def oio_platform_supported(installer: Path) -> tuple[bool, str]:
    """Ask the pinned OIO installer whether this platform can host it.

    The verdict comes from OIO's own platform dispatch, not from a copy of its
    precondition kept here. A copy is what went stale: this check kept
    reporting Windows unsupported after OIO gained a Windows backend, so an
    install that would have succeeded reported PARTIAL instead. When the pinned
    installer cannot answer at all — it predates the probe, and so predates the
    backend the probe would describe — this returns supported and lets OIO fail
    closed on its own terms rather than substituting a guess here.
    """
    try:
        probe = subprocess.run(
            [sys.executable, str(installer), "--check-platform"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return True, ""
    if probe.returncode == 1:
        reason = (probe.stdout or probe.stderr).strip()
        return False, reason or "the pinned OIO installer reports this platform unsupported"
    return True, ""


def adopter_state(adopter: Path) -> str:
    """Resolve the install state from the adopter's own records (SPEC.md section 3)."""
    if (adopter / OIO_JOURNAL_REL).is_file():
        return "RECOVERING"
    # The CGM adapter is a precondition the adopter must already carry, not a
    # component this installer writes, so it does not make a repo PARTIAL: a
    # repo with an adapter and no coordination surface is still a first install.
    present = [
        (adopter / ASSIGNMENT_REL).is_file(),
        (adopter / MANIFEST_REL).is_file(),
        (adopter / OIO_MANIFEST_REL).is_file(),
    ]
    if not any(present):
        return "ABSENT"
    if all(present):
        return "READY"
    return "PARTIAL"


def lock_drift(adopter: Path, requires: dict) -> list[str]:
    """Installed-vs-train drift: a lock that records older commits than the mesh."""
    try:
        lock = load_json(adopter / LOCK_REL)
    except (OSError, json.JSONDecodeError):
        return []
    checkouts = lock.get("checkouts", {}) if isinstance(lock, dict) else {}
    drift: list[str] = []
    for label, component in (
        ("pcm", "project-continuity-modules"),
        ("cgm", "content-generation-modules"),
        ("oio", OIO_COMPONENT),
    ):
        recorded = (checkouts.get(label) or {}).get("commit")
        wanted = (requires.get(component) or {}).get("commit")
        if recorded and wanted and not commits_agree(str(recorded), str(wanted)):
            drift.append(f"{label}: lock {short(str(recorded))} is behind mesh {short(str(wanted))}")
    return drift


def assignment_drift(adopter: Path, requires: dict) -> list[str]:
    """Installed-vs-train drift for the assignment's recorded revisions.

    ``assignment.json`` is managed but editable, so a re-run keeps it (SPEC.md
    section 4). When the train moves, the kept assignment still names the old
    revisions; without this check a re-run would install a mixed stack and never
    say so. Report it so the operator can re-run with ``--force``.
    """
    try:
        assignment = load_json(adopter / ASSIGNMENT_REL)
    except (OSError, json.JSONDecodeError):
        return []
    pins = assignment.get("pins", {}) if isinstance(assignment, dict) else {}
    if not isinstance(pins, dict):
        return []
    drift: list[str] = []
    for label, component in (
        ("pcm", "project-continuity-modules"),
        ("cgm", "content-generation-modules"),
    ):
        recorded = (pins.get(label) or {}).get("revision")
        wanted = (requires.get(component) or {}).get("commit")
        if recorded and wanted and not commits_agree(str(recorded), str(wanted)):
            drift.append(
                f"{label}: assignment records {short(str(recorded))} but the train is at "
                f"{short(str(wanted))}; re-run with --force to refresh it"
            )
    return drift


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


def snapshot(paths: list[Path]) -> dict[Path, bytes | None]:
    """Remember each target's bytes (None = did not exist) so writes can be undone."""
    saved: dict[Path, bytes | None] = {}
    for path in paths:
        try:
            saved[path] = path.read_bytes() if path.exists() else None
        except OSError:
            saved[path] = None
    return saved


def rollback(saved: dict[Path, bytes | None]) -> None:
    for path, original in saved.items():
        try:
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        except OSError:
            pass


def run_script(argv: list[str]) -> int:
    try:
        return subprocess.run(argv, check=False).returncode
    except OSError as exc:
        say(f"acs_install: could not run {argv[0]}: {exc}")
        return 1


def render_json_bytes(data: object) -> bytes:
    """Exactly the bytes ``write_json_atomic`` would produce, for equality checks."""
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def classify_owned(path: Path, adopter: Path) -> bool:
    """Whether a managed file is ours (SPEC.md section 5).

    Files in a component-owned directory (``.coord/``) are ours. A managed file
    outside one is ours only when it carries this pack's schema -- otherwise it
    is a hand-written foreign file we must not clobber.
    """
    try:
        rel = path.relative_to(adopter)
    except ValueError:
        return False
    if rel.parent == COORD_REL:
        return True
    try:
        data = load_json(path)
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and data.get("schema_version") == MANIFEST_SCHEMA


def gate_plan(
    targets: list[tuple[Path, object]], adopter: Path, *, force: bool
) -> tuple[list[tuple[Path, object]], list[tuple[Path, object]], list[str]]:
    """Classify every target path before any write (SPEC.md section 4).

    Returns ``(to_write, kept, refusals)``. A refusal means zero writes: the
    caller fails closed and reports it.
    """
    to_write: list[tuple[Path, object]] = []
    kept: list[tuple[Path, object]] = []
    refusals: list[str] = []
    for path, data in targets:
        rel = path.relative_to(adopter).as_posix()
        # Check the link itself, not what it points at: ``is_file()`` follows a
        # symlink, so a link to a regular file would otherwise pass as "ours" or
        # as foreign content instead of being refused (SPEC.md section 4).
        if path.is_symlink():
            refusals.append(f"{rel}: not a regular file (symlink or directory); refusing")
            continue
        if not path.exists():
            to_write.append((path, data))
            continue
        if not path.is_file():
            refusals.append(f"{rel}: not a regular file (symlink or directory); refusing")
            continue
        if classify_owned(path, adopter):
            (to_write if force else kept).append((path, data))
            continue
        try:
            identical = path.read_bytes() == render_json_bytes(data)
        except OSError:
            identical = False
        if identical:
            kept.append((path, data))  # adopt: foreign but byte-identical to ours
        else:
            refusals.append(
                f"{rel}: exists with foreign content; refusing to overwrite "
                "(move it aside or reconcile it, then re-run)"
            )
    return to_write, kept, refusals


def run(args: argparse.Namespace) -> int:
    acs_root = resolve_acs_root(args.acs_root)
    manifest_path = acs_root / DEFAULT_MANIFEST.relative_to(REPO_ROOT)
    try:
        manifest = load_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        say(f"acs_install: FAIL\n  - pins manifest unreadable: {manifest_path}: {exc}")
        return 2
    if not isinstance(manifest, dict) or not isinstance(manifest.get("pins"), dict):
        say(f"acs_install: FAIL\n  - {manifest_path} has no 'pins' object")
        return 2
    pins = copy.deepcopy(manifest["pins"])
    try:
        mesh_doc = load_json(acs_root / "stack-mesh.json")
    except (OSError, json.JSONDecodeError) as exc:
        say(f"acs_install: FAIL\n  - stack-mesh.json unreadable: {exc}")
        return 2
    if not isinstance(mesh_doc, dict) or not isinstance(mesh_doc.get("requires"), dict):
        say("acs_install: FAIL\n  - stack-mesh.json has no requires object")
        return 2
    requires = mesh_doc["requires"]
    pcm_req = requires.get("project-continuity-modules") or {}
    cgm_req = requires.get("content-generation-modules") or {}
    oio_req = requires.get(OIO_COMPONENT) or {}
    pins.setdefault("pcm", {})["commit"] = pcm_req.get("commit", "")
    pins["pcm"]["cli_version"] = pcm_req.get("version", "")
    pins.setdefault("cgm", {})["commit"] = cgm_req.get("commit", "")
    pins["cgm"]["version"] = cgm_req.get("version", "")

    problems: list[str] = []
    partials: list[str] = []

    # 1. The pack's own projections must agree before we touch anything.
    if run_script([sys.executable, str(CHECK_PINS), "--root", str(acs_root)]) != 0:
        problems.append(
            "pack pin drift: check_pins.py failed on the ACS checkout "
            f"({acs_root}); fix the pack before installing"
        )

    # 2. Adopter root must exist.
    adopter = args.adopter_root.expanduser().resolve()
    if not adopter.is_dir():
        say(f"acs_install: FAIL\n  - adopter root is not a directory: {adopter}")
        return 2

    state = adopter_state(adopter)
    drift = lock_drift(adopter, requires) + assignment_drift(adopter, requires)
    reported_state = "DRIFTED" if (state == "READY" and drift) else state

    # 3. A CGM adapter must already exist -- ACS does not author one.
    adapter = adopter / ADAPTER_REL
    if not adapter.is_dir():
        problems.append(
            f"adopter has no CGM adapter at {adapter} -- author the .content-system "
            "adapter first (CGM's job, not ACS's), then re-run; a partial install "
            "never looks complete"
        )

    # 4. Verify the pinned external checkouts (PCM, CGM, OIO).
    checkouts: dict[str, dict] = {}
    for label, root_arg, expected in (
        ("pcm", args.pcm_root, pins.get("pcm", {}).get("commit", "")),
        ("cgm", args.cgm_root, pins.get("cgm", {}).get("commit", "")),
        ("oio", args.oio_root, oio_req.get("commit", "")),
    ):
        if label == "oio" and root_arg is None:
            checkouts[label] = {"commit": None, "verified": False}
            continue
        errs = verify_checkout(root_arg, expected, label)
        problems.extend(errs)
        checkouts[label] = {
            "commit": git_head(root_arg.expanduser().resolve()) if root_arg else None,
            "verified": not errs,
        }

    # 5. OIO is a required component. Decide up front whether it can be installed;
    #    a component that cannot run makes the install PARTIAL, never a fake OK.
    oio_install = "not_run"
    oio_root = args.oio_root.expanduser().resolve() if args.oio_root else None
    if oio_root is None:
        partials.append(
            "OIO not installed: no --oio-root checkout provided; bring "
            f"{OIO_COMPONENT} at {short(oio_req.get('commit', ''))} and re-run"
        )
    else:
        installer = oio_root / OIO_INSTALLER_REL
        if not installer.is_file():
            problems.append(f"OIO checkout at {oio_root} has no {OIO_INSTALLER_REL.as_posix()}")
        else:
            supported, why = oio_platform_supported(installer)
            if not supported:
                partials.append(f"OIO not installed: {why}")
            else:
                oio_install = "pending"

    # 6. Build the coordination surface; keep existing files unless --force.
    try:
        example = load_json(EXAMPLE_ASSIGNMENT)
    except (OSError, json.JSONDecodeError) as exc:
        say(f"acs_install: FAIL\n  - assignment example unreadable: {exc}")
        return 2
    if not isinstance(example, dict):
        say("acs_install: FAIL\n  - assignment example is not a JSON object")
        return 2
    project_name = args.project_name or adopter.name
    project_id = args.project_id or None
    assignment = build_assignment(example, pins, project_name)
    try:
        stack_manifest = build_stack_manifest(mesh_doc, project_name)
    except ValueError as exc:
        say(f"acs_install: FAIL\n  - {exc}")
        return 2

    targets: list[tuple[Path, object]] = [
        (adopter / ASSIGNMENT_REL, assignment),
        (adopter / LOCK_REL, build_lock(pins, acs_root, checkouts, validated=False, state=reported_state)),
        (adopter / MANIFEST_REL, stack_manifest),
    ]
    to_write, kept, refusals = gate_plan(targets, adopter, force=args.force)
    problems.extend(refusals)

    # 7. Report the plan.
    say("acs_install: plan")
    say(f"  state={reported_state}")
    for item in drift:
        say(f"  drift {item}")
    say(f"  acs_root={acs_root}")
    say(f"  adopter_root={adopter}")
    say(
        f"  pcm_pin={short(pins.get('pcm', {}).get('commit'))}  "
        f"cgm_pin={short(pins.get('cgm', {}).get('commit'))}  "
        f"oio_pin={short(oio_req.get('commit', ''))}"
    )
    for path, _ in to_write:
        say(f"  write {path.relative_to(adopter)}")
    for path, _ in kept:
        say(f"  keep  {path.relative_to(adopter)} (exists; --force to overwrite)")
    if oio_install == "pending":
        say("  oio   install the OIO issue-log surface (invoke the pinned installer)")

    if problems:
        fail_state = "CONFLICTED" if refusals else reported_state
        say(f"acs_install: FAIL (state={fail_state}; nothing written)")
        for item in problems:
            for line in str(item).splitlines() or [str(item)]:
                say(f"  - {line}")
        return 1

    if args.dry_run:
        say("acs_install: dry-run OK (no files written)")
        return 0

    # 8. Write, then validate the whole stack with the pack's own checker.
    saved = snapshot([path for path, _ in to_write])
    for path, data in to_write:
        try:
            write_json_atomic(path, data, root=adopter)
        except (ValueError, OSError) as exc:
            rollback(saved)
            say(f"acs_install: FAIL (rolled back)\n  - {exc}")
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
        rollback(saved)
        say("acs_install: FAIL (hotload_check did not pass; writes rolled back)")
        return 1

    # 9. Install OIO last. Its installer is transactional on its own, so a failure
    #    here leaves a PARTIAL install (reported, never faked) rather than rolling
    #    back the coordination surface we just validated.
    if oio_install == "pending" and oio_root is not None:
        oio_argv = [sys.executable, str(oio_root / OIO_INSTALLER_REL), "--target", str(adopter)]
        if project_id:
            oio_argv += ["--project-id", project_id]
        rc = run_script(oio_argv)
        if rc == 0 and run_script(oio_argv + ["--check"]) == 0:
            oio_install = "OK"
        else:
            oio_install = "FAILED"
            partials.append(
                f"OIO install did not complete (exit {rc}); run: python "
                f"{OIO_INSTALLER_REL.as_posix()} --target <adopter>"
            )

    final_state = "PARTIAL" if partials else "READY"

    # 10. Refresh the lock now that validation passed.
    write_json_atomic(
        adopter / LOCK_REL,
        build_lock(
            pins, acs_root, checkouts, validated=True, state=final_state, oio_install=oio_install
        ),
        root=adopter,
    )

    if partials:
        say(f"acs_install: PARTIAL (state={final_state})")
        for item in partials:
            for line in str(item).splitlines() or [str(item)]:
                say(f"  - {line}")
        say("  the coordination surface is installed and valid; OIO is the remaining step")
        return 1

    say(f"acs_install: OK (state={final_state})")
    say(f"  wrote {ASSIGNMENT_REL.as_posix()}, {LOCK_REL.as_posix()} and {MANIFEST_REL.as_posix()}")
    say("  next: EDIT the assignment's agents list + check_in to match your seats/issue.")
    say("  next: add the train check to CI:")
    say("        uses: Pukujan/agent-stack-train/.github/workflows/check-adopter.yml@main")
    say("  next (human GitHub steps, NOT automated): enable branch protection on the")
    say("  default branch with the required CI checks, and turn on auto-merge so green")
    say("  required checks can merge without skipping gates.")
    return 0


def main(argv: list[str] | None = None) -> int:
    description = (__doc__ or "Install the ACS coordination surface into an adopter repo.").splitlines()[0]
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--adopter-root", type=Path, required=True)
    parser.add_argument("--acs-root", type=Path, default=None)
    parser.add_argument("--pcm-root", type=Path, default=None)
    parser.add_argument("--cgm-root", type=Path, default=None)
    parser.add_argument(
        "--oio-root",
        type=Path,
        default=None,
        help="observational-issue-ops checkout at the mesh commit; without it OIO is PARTIAL",
    )
    parser.add_argument("--project-name", type=str, default=None)
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="OWNER/REPOSITORY for the OIO project ontology (else OIO infers from origin)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show the plan; write nothing.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated files.")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
