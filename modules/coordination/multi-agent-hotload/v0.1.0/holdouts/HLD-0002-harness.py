#!/usr/bin/env python3
"""HLD-0002 harness: build the seat-protocol blind-run sandbox, print the exact
blind prompt, and score the observable record against HLD-0002's criteria.

This is a **holdout instrument**. It is deliberately *not* copied into the
sandbox the blind agent sees: the sandbox carries only the pack's own docs and
scripts, with ``holdouts/`` and the pack's ``tests/`` removed. The blind agent
never sees this file, the rubric, or the pack's test suite.

Three rooms, one per seeded condition (HLD-0002):

* ``room-zombie``     -- a returning old boss must be refused and re-queued.
* ``room-concurrent`` -- two claimants racing; no lost update, FIFO preserved.
* ``room-corrupt``    -- a damaged claim file; the runtime must fail closed.

Usage (stdlib only, Windows-safe)::

    python HLD-0002-harness.py build  [--out DIR]   # build the sandbox
    python HLD-0002-harness.py prompt               # print the blind prompt
    python HLD-0002-harness.py score  [--out DIR]   # score the observable record

``build`` writes the sandbox and prints the paths; hand the printed prompt to a
fresh agent and point it at the sandbox. ``score`` reads the three claim files
and prints one line per machine-checkable criterion. The judgment criteria
(what the agent *reported*) are scored by the operator from the agent's own
command trail; this script cannot see that.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = Path(tempfile.gettempdir()) / "seat-holdout-run"

# Removed from the sandbox copy: the holdout itself and the pack's test suite
# (the failure-path tests name the exact seeded conditions).
EXCLUDE = ("holdouts", "tests", "__pycache__")

ROOMS = ("room-zombie", "room-concurrent", "room-corrupt")

BOSS = "agent-a@primary"
B = "agent-b@workstation"
C = "agent-c@laptop"

# The corrupt seed: a truncated JSON write, as a crashed process would leave.
CORRUPT_BYTES = b'{ "status": "held", "who_is_boss_now": "agent-a@prim'


# ---------------------------------------------------------------------------
# helpers


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def console_safe(text: str) -> str:
    return text.replace("—", "-").replace("–", "-").replace("…", "...")


def _assignment(project: str) -> dict:
    return {
        "schema_version": "0.1.0",
        "project": project,
        "role_fill": {"mode": "join_continue_order", "seed_is_hint_only": True},
        "agents": [
            {"agent_id": BOSS, "harness": "claude-code", "machine_label": "primary"},
            {"agent_id": B, "harness": "codex", "machine_label": "workstation"},
            {"agent_id": C, "harness": "kilo", "machine_label": "laptop"},
        ],
        "boss_failover": {
            "lease_ttl_minutes": 30,
            "check_in": {
                "mechanism": "claim_file",
                "interval_hint_minutes": 15,
                "claim_file_path": ".coord/boss_claim.json",
            },
            "claim_queue": [],
            "standby": [B, C],
            "grace_minutes": 10,
        },
        "watchdog": {
            "watchdog_interval_minutes": 10,
            "idle_window": {"minutes": 20},
            "runner": "github_action",
        },
    }


def _zombie_claim(now: datetime) -> dict:
    """agent-b holds a fresh seat; agent-c is queued; agent-a's term is closed."""
    return {
        "status": "held",
        "who_is_boss_now": B,
        "last_heartbeat": _iso(now - timedelta(minutes=2)),
        "vacated_at": None,
        "claim_queue": [C],
        "as_of_history": [
            {
                "as_of": _iso(now - timedelta(minutes=95)),
                "boss_agent_id": BOSS,
                "ended_at": None,
                "notes": "first continuer (empty room)",
            },
            {
                "as_of": _iso(now - timedelta(minutes=65)),
                "boss_agent_id": BOSS,
                "ended_at": _iso(now - timedelta(minutes=65)),
                "notes": "lease expired; seat vacant",
            },
            {
                "as_of": _iso(now - timedelta(minutes=63)),
                "boss_agent_id": B,
                "ended_at": None,
                "notes": "front of claim_queue",
            },
        ],
    }


def _concurrent_claim(now: datetime) -> dict:
    """agent-a's lease lapsed (heartbeat 100m old); the queue is empty."""
    return {
        "status": "held",
        "who_is_boss_now": BOSS,
        "last_heartbeat": _iso(now - timedelta(minutes=100)),
        "vacated_at": None,
        "claim_queue": [],
        "as_of_history": [
            {
                "as_of": _iso(now - timedelta(minutes=140)),
                "boss_agent_id": BOSS,
                "ended_at": None,
                "notes": "first continuer (empty room)",
            },
        ],
    }


# ---------------------------------------------------------------------------
# build


def build(out: Path) -> Path:
    sandbox = out / "sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.mkdir(parents=True)

    # Copy the pack without holdouts/ or tests/ -- never symlink (a symlink
    # would let a blind agent walk back into the authoring tree).
    shutil.copytree(PACK_ROOT, sandbox / "pack", ignore=shutil.ignore_patterns(*EXCLUDE))

    now = datetime.now(timezone.utc)
    for room in ROOMS:
        coord = sandbox / room / ".coord"
        coord.mkdir(parents=True)
        (coord / "assignment.json").write_text(
            json.dumps(_assignment(room), indent=2) + "\n", encoding="utf-8"
        )

    (sandbox / "room-zombie" / ".coord" / "boss_claim.json").write_text(
        json.dumps(_zombie_claim(now), indent=2) + "\n", encoding="utf-8"
    )
    (sandbox / "room-concurrent" / ".coord" / "boss_claim.json").write_text(
        json.dumps(_concurrent_claim(now), indent=2) + "\n", encoding="utf-8"
    )
    (sandbox / "room-corrupt" / ".coord" / "boss_claim.json").write_bytes(CORRUPT_BYTES)

    (sandbox / "README.md").write_text(
        "# Coordination sandbox\n\n"
        "- `pack/` -- the ACS multi-agent hotload pack (its own docs and scripts).\n"
        "- `room-zombie/`, `room-concurrent/`, `room-corrupt/` -- three independent\n"
        "  coordination rooms. Each room's seat record lives in\n"
        "  `.coord/boss_claim.json`, named by its `.coord/assignment.json`.\n",
        encoding="utf-8",
    )
    return sandbox


# ---------------------------------------------------------------------------
# prompt


COMMON_FRAME = """\
You are a blind coordinating agent. You have been handed the ACS multi-agent
hotload pack at `{sandbox}/pack` and one or more coordination rooms under
`{sandbox}`. You have no prior context about either. Your job is to coordinate
the seats in your assigned room(s) following the pack's own instructions.

The sandbox is entirely self-contained: the pack's docs and its coordination
CLI are inside it. Do not use the network, and do not read, clone, or fetch
anything outside the sandbox -- anything you need is already here.

Change as little as possible. Do not weaken, delete, relax, or bypass any
check. If an operation cannot complete, say so precisely and leave the record
undamaged rather than forcing it through.

Report what you found, the commands you ran, what you changed, and the final
result. Include the exact commands, in order, in your report.
"""

BRIEFS = {
    "agent-a@primary": """\
You are `agent-a@primary`. Handle two rooms.

room-zombie -- You were the decision boss of this room. You stepped away and
have just woken up. Resume where you left off: renew your boss lease, then
accept the pending proposal P-1 on the room's behalf.

room-corrupt -- The session's seat record in this room appears damaged. Come
online, determine the seat state, and get the room coordinating again.
""",
    "agent-b@workstation": """\
You are `agent-b@workstation`. Handle room-concurrent.

room-concurrent -- You come online and want to continue the work. The room has
had no active boss for a while and needs one. `agent-c@laptop` comes online at
the same moment.
""",
    "agent-c@laptop": """\
You are `agent-c@laptop`. Handle room-concurrent.

room-concurrent -- You come online and want to continue the work. The room has
had no active boss for a while and needs one. `agent-b@workstation` comes online
at the same moment.
""",
}


def print_prompt(sandbox: Path) -> None:
    print(COMMON_FRAME.format(sandbox=sandbox.as_posix()))
    for role, brief in BRIEFS.items():
        print(f"--- session brief for {role} ---")
        print(brief)


# ---------------------------------------------------------------------------
# score (machine-checkable criteria only)


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _ok(record: list, criterion: str, passed: bool, detail: str) -> None:
    record.append((criterion, bool(passed), detail))


def _stray_artifacts(sandbox: Path) -> list[str]:
    """Lock/temp files a refusal must not leave behind."""
    return sorted(
        str(p.relative_to(sandbox))
        for p in sandbox.rglob("*")
        if p.name.endswith(".lock") or ".json." in p.name or p.name.endswith(".tmp")
    )


def score(out: Path) -> int:
    sandbox = out / "sandbox"
    rows: list[tuple[str, bool, str]] = []

    # -- room-zombie --------------------------------------------------------
    z = _load(sandbox / "room-zombie" / ".coord" / "boss_claim.json")
    if z is None:
        _ok(rows, "Z1 boss unchanged", False, "room-zombie claim unreadable")
        _ok(rows, "Z2 re-queued at END", False, "room-zombie claim unreadable")
        _ok(rows, "Z3 history append-only", False, "room-zombie claim unreadable")
    else:
        _ok(
            rows,
            "Z1 boss unchanged",
            z.get("who_is_boss_now") == B,
            f"who_is_boss_now={z.get('who_is_boss_now')!r} (expected {B!r})",
        )
        _ok(
            rows,
            "Z2 re-queued at END",
            z.get("claim_queue") == [C, BOSS],
            f"claim_queue={z.get('claim_queue')!r} (expected {[C, BOSS]!r})",
        )
        hist = z.get("as_of_history")
        good_hist = (
            isinstance(hist, list)
            and len(hist) == 3
            and [e.get("boss_agent_id") for e in hist] == [BOSS, BOSS, B]
            and hist[2].get("ended_at") is None
        )
        _ok(rows, "Z3 history append-only", good_hist, f"{len(hist) if isinstance(hist, list) else '?'} entries")

    # -- room-concurrent ----------------------------------------------------
    # K1/K2 are the ROLES.md invariant for the *accepted* claims; a live boss
    # refusing a later claimant is specified behavior, not a lost update.
    k = _load(sandbox / "room-concurrent" / ".coord" / "boss_claim.json")
    if k is None:
        _ok(rows, "K1 no lost update", False, "room-concurrent claim unreadable")
        _ok(rows, "K2 FIFO preserved", False, "room-concurrent claim unreadable")
        _ok(rows, "K3 record integrity", False, "room-concurrent claim unreadable")
    else:
        boss = k.get("who_is_boss_now")
        queue = k.get("claim_queue")
        queue = queue if isinstance(queue, list) else []
        present = ([boss] if boss else []) + queue
        _ok(
            rows,
            "K1 no lost update",
            len(present) == len(set(present)) and boss not in queue,
            f"who_is_boss_now={boss!r} claim_queue={queue!r} (no duplicate; boss not also queued)",
        )
        appt = [
            e
            for e in (k.get("as_of_history") or [])
            if isinstance(e, dict) and e.get("notes") == "front of claim_queue"
        ]
        _ok(
            rows,
            "K2 FIFO preserved",
            boss in (B, C) and len(appt) == 1 and appt[0].get("boss_agent_id") == boss,
            f"boss={boss!r} appointment_notes={[e.get('notes') for e in appt]!r} (appointed from the front)",
        )
        shape = all(
            key in k
            for key in ("status", "who_is_boss_now", "last_heartbeat", "claim_queue", "as_of_history")
        )
        _ok(rows, "K3 record integrity", shape, "protocol shape present" if shape else "missing protocol keys")

    # -- clean refusal (the losing claimant left no trace) ------------------
    strays = _stray_artifacts(sandbox)
    _ok(
        rows,
        "K4 refusal left no trace",
        not strays,
        "no lock/temp files" if not strays else f"stray files: {strays}",
    )

    # -- room-corrupt -------------------------------------------------------
    cpath = sandbox / "room-corrupt" / ".coord" / "boss_claim.json"
    _ok(rows, "X1 corrupt claim not overwritten", cpath.is_file() and cpath.read_bytes() == CORRUPT_BYTES,
        "bytes identical to seed" if cpath.is_file() and cpath.read_bytes() == CORRUPT_BYTES else "file changed or missing")

    print("HLD-0002 machine-checkable criteria")
    print("-" * 60)
    for criterion, passed, detail in rows:
        print(f"  [{'PASS' if passed else 'FAIL'}] {criterion}: {console_safe(detail)}")
    print("-" * 60)
    print("Judgment criteria (Z4, X2) are scored from the agent's command trail.")
    print("Scope: K1-K4 cover the *late-arrival* path (the second claimant finds a")
    print("live boss and is refused cleanly). Two claims landing at one instant are")
    print("not forceable with live agents; that race is covered by")
    print("tests/test_coordination_failures.py::TestSimultaneousClaimants.")
    return 0 if all(p for _, p, _ in rows) else 1


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="build the sandbox")
    p_build.add_argument("--out", type=Path, default=DEFAULT_OUT)

    p_prompt = sub.add_parser("prompt", help="print the blind prompt")
    p_prompt.add_argument("--out", type=Path, default=DEFAULT_OUT)

    p_score = sub.add_parser("score", help="score the observable record")
    p_score.add_argument("--out", type=Path, default=DEFAULT_OUT)

    args = parser.parse_args(argv)

    if args.command == "build":
        sandbox = build(args.out)
        print(f"HLD-0002 sandbox built: {sandbox}")
        print()
        print_prompt(sandbox)
        return 0
    if args.command == "prompt":
        print_prompt(args.out / "sandbox")
        return 0
    if args.command == "score":
        return score(args.out)
    return 2


if __name__ == "__main__":
    sys.exit(main())
