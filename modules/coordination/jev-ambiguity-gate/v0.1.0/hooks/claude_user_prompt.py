#!/usr/bin/env python3
"""Claude Code UserPromptSubmit / SessionStart hook → ambiguity gate.

Reads hook JSON on stdin; writes Claude-compatible JSON decision on stdout.
Exit 0 always for soft-ask; use permissionDecision ask/deny when ambiguous.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "jev-shared" / "v0.1.0" / "scripts"))

from ambiguity_gate import judge  # noqa: E402

def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}
    prompt = data.get("prompt") or data.get("user_prompt") or ""
    resume = data.get("resume_context") or data.get("session_summary") or ""
    event = data.get("hook_event_name") or data.get("event") or "UserPromptSubmit"
    decision, reason = judge(prompt, resume, "mock")
    # Map to Claude hook permissionDecision
    if decision == "clear":
        perm = "allow"
    elif decision == "ambiguous":
        perm = "ask"
    else:
        perm = "ask"
    out = {
        "hookSpecificOutput": {
            "hookEventName": event if event in ("UserPromptSubmit", "SessionStart") else "UserPromptSubmit",
            "permissionDecision": perm,
            "permissionDecisionReason": f"ambiguity_gate:{decision}:{reason}",
        }
    }
    # Also support older block shape
    if decision == "ambiguous":
        out["decision"] = "block"
        out["reason"] = f"Ambiguous prompt — clarify before acting ({reason})"
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
