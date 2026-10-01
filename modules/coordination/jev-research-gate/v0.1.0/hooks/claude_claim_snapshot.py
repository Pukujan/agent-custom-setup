#!/usr/bin/env python3
"""Claude hook-style claim snapshot runner (SessionStart / manual)."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from research_gate import judge  # noqa: E402

def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        data = {}
    claim = data.get("claim_text") or data.get("prompt") or ""
    docs = list(data.get("known_docs") or [])
    decision, reason = judge(claim, docs, "mock")
    out = {
        "gate_kind": "research",
        "decision": decision,
        "reason_code": reason,
        "fallback": "#14 checklist if insufficient",
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": f"research_gate={decision} ({reason}); fallback=#14 if insufficient"
        }
    }
    json.dump(out, sys.stdout); print()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
