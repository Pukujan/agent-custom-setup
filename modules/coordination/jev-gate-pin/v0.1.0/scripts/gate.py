#!/usr/bin/env python3
"""PreToolUse-style gate CLI for jev-gate-pin.

Decisions: allow | deny | escalate.

Judges:
  --judge mock (default): Fish-class heuristic rules for fixtures/CI.
  --judge inferhub: fails closed with escalate unless env clearly configured
                    (does not call paid APIs by default).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from gather import build_package  # noqa: E402
from log_event import append_event, make_event  # noqa: E402

SELFHOST_RE = re.compile(
    r"(fish-speech|run_selfhost|selfhost_server|pip\s+install[^\n]*fish|git\s+clone[^\n]*fish)",
    re.I,
)
HOSTED_API_RE = re.compile(
    r"(fish\.audio|api\.fish\.audio|hosted\s+api|/v1/tts)",
    re.I,
)
HOSTED_BRIEF_RE = re.compile(
    r"(hosted|fish\.audio|MUST\s+use\s+.*hosted|do\s+not\s+self[- ]?host)",
    re.I,
)


def mock_judge(pkg: Dict[str, Any]) -> Tuple[str, str]:
    """Simple Fish-class rules.

    - Hosted brief + self-host action tool (clone/pip fish-speech) -> deny
    - Proposed fish.audio hosted API call -> allow
    - Otherwise allow (low-risk / non-Fish)
    """
    briefish = " ".join(
        [str(pkg.get("pinned_brief") or "")] + list(pkg.get("corrections") or [])
    )
    pt = pkg.get("proposed_tool") or {}
    tool_blob = f"{pt.get('name', '')} {pt.get('args_summary', '')}"

    hosted_brief = bool(HOSTED_BRIEF_RE.search(briefish))
    selfhost_tool = bool(SELFHOST_RE.search(tool_blob))
    hosted_tool = bool(HOSTED_API_RE.search(tool_blob))

    if hosted_brief and selfhost_tool:
        return "deny", "fish_hosted_brief_selfhost_tool"
    if hosted_tool:
        return "allow", "fish_hosted_api_tool"
    return "allow", "mock_default_allow"


def inferhub_judge(pkg: Dict[str, Any]) -> Tuple[str, str]:
    """Stub: fail closed with escalate unless clearly configured.

    Does not call paid APIs unless env clearly set. Prefer mock for CI.
    """
    enabled = os.environ.get("JEV_INFERHUB_GATE_ENABLED", "").strip().lower()
    endpoint = os.environ.get("JEV_INFERHUB_ENDPOINT", "").strip()
    if enabled in ("1", "true", "yes") and endpoint:
        return "escalate", "inferhub_not_implemented_fail_closed"
    return "escalate", "inferhub_not_configured_fail_closed"


def judge_package(pkg: Dict[str, Any], judge: str) -> Tuple[str, str]:
    if judge == "mock":
        return mock_judge(pkg)
    if judge == "inferhub":
        return inferhub_judge(pkg)
    return "escalate", f"unknown_judge_{judge}"


def load_package(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_to_package(fx: Dict[str, Any]) -> Dict[str, Any]:
    return build_package(
        brief=fx.get("brief") or "",
        corrections=list(fx.get("corrections") or []),
        proposed_tool=dict(fx.get("proposed_tool") or {}),
        fixture_id=fx.get("id"),
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="jev-gate-pin PreToolUse-style gate")
    ap.add_argument("--package", help="Path to gather package JSON")
    ap.add_argument("--fixture", help="Path to fixture JSON (builds package)")
    ap.add_argument("--judge", choices=["mock", "inferhub"], default="mock")
    ap.add_argument("--log", help="Optional JSONL path to append gate event")
    ap.add_argument("--json", action="store_true", help="Emit full JSON result")
    args = ap.parse_args(argv)

    if not args.package and not args.fixture:
        ap.error("provide --package or --fixture")

    fixture_id = None
    gold = None
    if args.fixture:
        fx = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        fixture_id = fx.get("id")
        gold = fx.get("gold_decision")
        pkg = fixture_to_package(fx)
    else:
        pkg = load_package(Path(args.package))
        fixture_id = pkg.get("fixture_id")

    decision, reason = judge_package(pkg, args.judge)
    tool_name = (pkg.get("proposed_tool") or {}).get("name") or "unknown"

    result = {
        "decision": decision,
        "reason_code": reason,
        "tool_name": tool_name,
        "judge": args.judge,
        "fixture_id": fixture_id,
        "gold_decision": gold,
    }

    if args.log:
        ev = make_event(
            decision=decision,
            tool_name=tool_name,
            reason_code=reason,
            fixture_id=fixture_id,
            judge=args.judge,
        )
        append_event(Path(args.log), ev)

    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(f"{decision}\t{reason}\n")

    if decision == "allow":
        return 0
    if decision == "deny":
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
