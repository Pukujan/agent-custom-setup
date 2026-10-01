#!/usr/bin/env python3
"""Claude Code PreToolUse hook → jev-gate-pin.

stdin: Claude hook JSON with tool_name / tool_input.
stdout: hookSpecificOutput permissionDecision allow|deny|ask.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from gather import build_package  # noqa: E402
from gate import judge_package  # noqa: E402

def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        data = {}
    tool_name = data.get("tool_name") or data.get("toolName") or ""
    tool_input = data.get("tool_input") or data.get("toolInput") or {}
    brief = data.get("pinned_brief") or data.get("brief") or ""
    corrections = list(data.get("corrections") or [])
    args_summary = json.dumps(tool_input, ensure_ascii=False)[:1500]
    pkg = build_package(brief=brief, corrections=corrections,
                        proposed_tool={"name": tool_name, "args_summary": args_summary})
    decision, reason = judge_package(pkg, "mock")
    perm = {"allow": "allow", "deny": "deny", "escalate": "ask"}.get(decision, "ask")
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": perm,
            "permissionDecisionReason": f"jev-gate-pin:{decision}:{reason}",
        },
        "gate_kind": "tool_pin",
        "decision": decision,
        "reason_code": reason,
    }
    if decision == "deny":
        out["decision"] = "block"  # legacy field; real decision also in gate fields
        out["reason"] = f"Blocked by jev-gate-pin ({reason})"
        out["gate_decision"] = "deny"
    json.dump(out, sys.stdout); print()
    return 0 if decision == "allow" else 2

if __name__ == "__main__":
    raise SystemExit(main())
