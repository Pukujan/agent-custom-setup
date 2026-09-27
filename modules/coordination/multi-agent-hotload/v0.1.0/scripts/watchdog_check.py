#!/usr/bin/env python3
"""Agent-less boss-seat watchdog skeleton.

Run via cron, GitHub Action, or plain script — NEVER via an LLM or peer agent.
Reads claim heartbeat + optional GitHub stamps. Writes vacant after lease TTL.
No product decisions. No boss appointment.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def hours_since(ts: datetime | None, now: datetime) -> float | None:
    if ts is None:
        return None
    return (now - ts).total_seconds() / 3600.0


def evaluate(
    *,
    last_heartbeat: datetime | None,
    last_github_activity: datetime | None,
    lease_ttl_hours: float,
    idle_window_minutes: float,
    now: datetime | None = None,
) -> str:
    """Return noop | nudge_keep_boss | flag_at_risk | vacant."""
    now = now or datetime.now(timezone.utc)
    age_h = hours_since(last_heartbeat, now)
    if age_h is None:
        return "vacant"
    if age_h <= lease_ttl_hours:
        # Within lease: distinguish fresh vs stale-idle vs stale-with-activity
        idle_h = idle_window_minutes / 60.0
        if age_h <= idle_h:
            return "noop"
        gh_age_h = hours_since(last_github_activity, now)
        if gh_age_h is not None and gh_age_h <= idle_h:
            return "nudge_keep_boss"
        return "flag_at_risk"
    return "vacant"


def load_claim(path: Path) -> dict:
    if not path.is_file():
        return {"status": "vacant", "last_heartbeat": None}
    with path.open(encoding="utf-8-sig") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {"status": "vacant"}


def write_vacant(path: Path, claim: dict) -> None:
    claim = dict(claim)
    claim["status"] = "vacant"
    claim["vacated_at"] = datetime.now(timezone.utc).isoformat()
    claim["who_is_boss_now"] = None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(claim, indent=2) + "\n", encoding="utf-8")


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
    ttl = float(bf.get("lease_ttl_hours", 12))
    idle = float((wd.get("idle_window") or {}).get("minutes", 45))
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
        lease_ttl_hours=ttl,
        idle_window_minutes=idle,
    )
    print(f"watchdog_check: {decision}")
    print("  runner=agent-less (cron|action|script); no LLM")
    print(f"  lease_ttl_hours={ttl} idle_window_minutes={idle}")
    print(f"  claim_file={claim_path}")
    if decision == "vacant" and not args.dry_run:
        write_vacant(claim_path, claim)
        print("  wrote status=vacant (agents may claim; watchdog does not appoint)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
