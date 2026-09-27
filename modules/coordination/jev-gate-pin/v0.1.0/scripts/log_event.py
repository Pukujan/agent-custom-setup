#!/usr/bin/env python3
"""Append compact JSONL gate events; redact obvious secret-looking values."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

SECRETISH = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization|bearer)\s*[=:]\s*\S+"
)
LONG_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")
SK_PREFIX = re.compile(r"\b(sk|pk|ghp|gho|xox[baprs])-[A-Za-z0-9_-]{8,}\b")


def redact(text: str) -> str:
    if not text:
        return text
    out = SECRETISH.sub(r"\1=[REDACTED]", text)
    out = SK_PREFIX.sub("[REDACTED]", out)
    out = LONG_HEX.sub("[REDACTED]", out)
    return out


def make_event(
    *,
    decision: str,
    tool_name: str,
    reason_code: str,
    fixture_id: Optional[str] = None,
    judge: str = "mock",
    notes: str = "",
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    if ts is None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ev: Dict[str, Any] = {
        "ts": ts,
        "decision": decision,
        "tool_name": redact(tool_name),
        "reason_code": reason_code,
        "judge": judge,
    }
    if fixture_id is not None:
        ev["fixture_id"] = fixture_id
    if notes:
        ev["notes"] = redact(notes)
    return ev


def append_event(path: Path, event: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Redact string fields defensively
    safe = {k: (redact(v) if isinstance(v, str) else v) for k, v in event.items()}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(safe, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Append a gate event JSONL line")
    ap.add_argument("--log", required=True, help="JSONL path")
    ap.add_argument("--decision", required=True, choices=["allow", "deny", "escalate"])
    ap.add_argument("--tool-name", required=True)
    ap.add_argument("--reason-code", required=True)
    ap.add_argument("--fixture-id", default=None)
    ap.add_argument("--judge", default="mock")
    ap.add_argument("--notes", default="")
    args = ap.parse_args(argv)
    ev = make_event(
        decision=args.decision,
        tool_name=args.tool_name,
        reason_code=args.reason_code,
        fixture_id=args.fixture_id,
        judge=args.judge,
        notes=args.notes,
    )
    append_event(Path(args.log), ev)
    sys.stdout.write(json.dumps(ev) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
