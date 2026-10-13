#!/usr/bin/env python3
"""Agent-less boss-seat watchdog skeleton.

Run via cron, GitHub Action, or plain script — NEVER via an LLM or peer agent.
Reads claim heartbeat + optional GitHub stamps. Writes vacant after lease TTL.
No product decisions. No boss appointment. Claimants enqueue on the claim
queue via the seat runtime (scripts/seat_protocol.py); the watchdog never
appoints and never reorders the queue.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import seat_protocol  # noqa: E402  (sibling script; stdlib only)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def minutes_since(ts: datetime | None, now: datetime) -> float | None:
    if ts is None:
        return None
    return (now - ts).total_seconds() / 60.0


def evaluate(
    *,
    last_heartbeat: datetime | None,
    last_github_activity: datetime | None,
    lease_ttl_minutes: float,
    idle_window_minutes: float,
    now: datetime | None = None,
) -> str:
    """Return noop | nudge_keep_boss | flag_at_risk | vacant.

    The liveness tiering (fresh / nudge / at-risk) is watchdog-only; the
    lease decision itself (past TTL means the lease is gone) is delegated to
    the seat runtime's ``evaluate_lease`` so there is exactly one lease
    implementation in the pack.
    """
    now = now or datetime.now(timezone.utc)
    age_m = minutes_since(last_heartbeat, now)
    if age_m is None:
        return "vacant"
    if seat_protocol.evaluate_lease(last_heartbeat, lease_ttl_minutes, now):
        # Within lease: distinguish fresh vs stale-idle vs stale-with-activity
        if age_m <= idle_window_minutes:
            return "noop"
        gh_age_m = minutes_since(last_github_activity, now)
        if gh_age_m is not None and gh_age_m <= idle_window_minutes:
            return "nudge_keep_boss"
        return "flag_at_risk"
    return "vacant"


def load_claim(path: Path) -> dict:
    """Read the claim; an absent file is a fresh vacant record.

    A present-but-corrupt file fails closed (named reason) rather than being
    treated as vacant: overwriting a record we failed to parse would lose the
    seat state the protocol is supposed to protect.
    """
    if not path.is_file():
        return {
            "status": "vacant",
            "who_is_boss_now": None,
            "last_heartbeat": None,
            "claim_queue": [],
        }
    try:
        return seat_protocol.normalise_claim(path.read_bytes())
    except seat_protocol.CorruptClaimFileError:
        raise


def write_vacant(path: Path, claim: dict, *, now: datetime | None = None) -> None:
    """Write the seat vacant after lease TTL, via the seat runtime.

    Delegates to ``SeatMachine.expire`` so the one seat-changing path the
    watchdog owns goes through the same state machine as every agent
    transition — including appending as-of history (ROLES.md step 6), which
    this function previously skipped. The runtime expires the seat only when
    the recorded heartbeat is actually past TTL; it never appoints, never
    reorders ``claim_queue``, and is idempotent when the seat is already
    vacant. Unknown keys on the record are preserved.
    """
    ttl = float(claim.get("lease_ttl_minutes") or 30.0)
    machine = seat_protocol.SeatMachine(
        seat_protocol.LocalFileClaimStore(path), lease_ttl_minutes=ttl
    )
    machine.expire(now or datetime.now(timezone.utc))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--assignment",
        type=Path,
        default=MODULE_ROOT / "examples" / "assignment.example.json",
    )
    p.add_argument(
        "--claim-file",
        type=Path,
        default=None,
        help="Override claim file path (else from assignment check_in.claim_file_path)",
    )
    p.add_argument(
        "--github-last-activity",
        default=None,
        help="ISO timestamp of latest commit/PR activity (injected by CI; optional)",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    with args.assignment.open(encoding="utf-8-sig") as fh:
        assignment = json.load(fh)
    bf = assignment.get("boss_failover") or {}
    wd = assignment.get("watchdog") or {}
    # Prefer minutes; reject legacy hours-only configs by falling through to default 30.
    if "lease_ttl_minutes" in bf:
        ttl = float(bf["lease_ttl_minutes"])
    else:
        ttl = 30.0
    idle = float((wd.get("idle_window") or {}).get("minutes", 20))
    check_in = bf.get("check_in") or {}
    claim_path = args.claim_file or Path(
        check_in.get("claim_file_path") or ".coord/boss_claim.json"
    )
    if not claim_path.is_absolute():
        # resolve relative to CWD (consuming repo), not module root
        claim_path = Path.cwd() / claim_path

    claim = load_claim(claim_path)
    last_hb = parse_dt(claim.get("last_heartbeat"))
    last_gh = parse_dt(args.github_last_activity) or parse_dt(claim.get("last_github_activity"))
    decision = evaluate(
        last_heartbeat=last_hb,
        last_github_activity=last_gh,
        lease_ttl_minutes=ttl,
        idle_window_minutes=idle,
    )
    print(f"watchdog_check: {decision}")
    print("  runner=agent-less (cron|action|script); no LLM")
    print(f"  lease_ttl_minutes={ttl} idle_window_minutes={idle}")
    print(f"  claim_file={claim_path}")
    if decision == "vacant" and not args.dry_run:
        # The runtime's expire appends as-of history (append-only) and never
        # appoints; the lease TTL lives on the record so the seat state
        # machine and this liveness pass agree on one TTL.
        claim["lease_ttl_minutes"] = ttl
        write_vacant(claim_path, claim)
        print("  wrote status=vacant (agents enqueue on the claim queue; watchdog does not appoint)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
