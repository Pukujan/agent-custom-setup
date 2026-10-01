#!/usr/bin/env python3
"""Ambiguity gate CLI — clear | ambiguous | insufficient."""
from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path(__file__).resolve().parents[3] / "jev-shared" / "v0.1.0" / "scripts"
for p in (SHARED,):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from ops_db import append_gate_event  # noqa: E402
from openrouter_jev import decide_openrouter, env_live_enabled  # noqa: E402

VAGUE = re.compile(r"\b(somehow|whatever|maybe|you know|thing|stuff|idk|not sure|or not)\b", re.I)
ACTIONABLE = re.compile(r"\b(add|fix|implement|write|create|test|pytest|refactor|docs?|MUST|do not)\b", re.I)

def mock_judge(prompt: str, resume: str) -> Tuple[str, str]:
    text = (prompt or "").strip()
    ctx = (resume or "").strip()
    if not text and (not ctx or ctx.lower() in ("(truncated)", "truncated", "...")):
        return "insufficient", "empty_or_truncated_resume"
    # Vague markers dominate — even if a weak action verb appears ("fix it somehow").
    if VAGUE.search(text):
        return "ambiguous", "vague_markers"
    if ACTIONABLE.search(text) and len(text) >= 20:
        return "clear", "actionable_prompt"
    if len(text) < 8:
        return "insufficient", "too_short"
    return "clear", "mock_default_clear"


def live_judge(prompt: str, resume: str) -> Tuple[str, str]:
    state = f"PROMPT:\\n{(prompt or '')[:2000]}\\n\\nRESUME_CONTEXT:\\n{(resume or '')[:1000]}"
    try:
        choice, conf, mid = decide_openrouter(
            state=state,
            question_name="ambiguity",
            instructions="Is this user prompt/resume clear enough to act without clarification?",
            criteria={
                "clear": "specific actionable request with enough context",
                "ambiguous": "under-specified, conflicting, or refers to unclear prior context",
                "insufficient": "missing prompt/context; cannot judge",
            },
        )
    except Exception as e:
        return "insufficient", f"live_error_{type(e).__name__}"
    if choice not in ("clear", "ambiguous", "insufficient"):
        choice = "insufficient"
    return choice, f"live_{mid}_c{conf:.2f}"

def judge(prompt: str, resume: str, mode: str) -> Tuple[str, str]:
    if mode == "mock":
        return mock_judge(prompt, resume)
    if mode == "openrouter":
        if not env_live_enabled():
            return "insufficient", "live_not_enabled"
        return live_judge(prompt, resume)
    return "insufficient", f"unknown_judge_{mode}"

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--resume", default="")
    ap.add_argument("--judge", choices=["mock", "openrouter"], default="mock")
    ap.add_argument("--session-id", default=None)
    ap.add_argument("--log", default=None, help="optional JSONL")
    ap.add_argument("--ops-db", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    gold = None
    fid = None
    event = "UserPromptSubmit"
    if args.fixture:
        fx = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        prompt, resume = fx.get("prompt") or "", fx.get("resume_context") or ""
        gold, fid, event = fx.get("gold_decision"), fx.get("id"), fx.get("event") or event
    else:
        prompt, resume = args.prompt, args.resume
    decision, reason = judge(prompt, resume, args.judge)
    result = {"decision": decision, "reason_code": reason, "judge": args.judge,
              "gate_kind": "ambiguity", "fixture_id": fid, "gold_decision": gold, "event": event}
    dbp = Path(args.ops_db) if args.ops_db else None
    try:
        append_gate_event(gate_kind="ambiguity", decision=decision, reason_code=reason,
                          tool_name=event, judge=args.judge, notes=(prompt or "")[:200],
                          session_id=args.session_id, payload={"fixture_id": fid}, db_path=dbp)
    except Exception as _ops_err:
        result["ops_db_error"] = type(_ops_err).__name__
    if args.log:
        from pathlib import Path as P
        p = P(args.log); p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**result, "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}) + "\n")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{decision}\\t{reason}")
    return 0 if decision == "clear" else (2 if decision == "ambiguous" else 3)

if __name__ == "__main__":
    raise SystemExit(main())
