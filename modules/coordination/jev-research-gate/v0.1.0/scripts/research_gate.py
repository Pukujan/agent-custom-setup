#!/usr/bin/env python3
"""Research-needed gate — yes | no | insufficient."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from typing import List, Tuple

SHARED = Path(__file__).resolve().parents[3] / "jev-shared" / "v0.1.0" / "scripts"
sys.path.insert(0, str(SHARED))
from ops_db import append_gate_event, append_issue_snapshot  # noqa: E402
from openrouter_jev import decide_openrouter, env_live_enabled  # noqa: E402

EXT = re.compile(r"\b(docs?|api|official|upstream|version|bump|release|sdk|hooks?\s+semantics|changelog)\b", re.I)
LOCAL = re.compile(r"\b(unit test|pytest|in-repo|fixture|local|no external)\b", re.I)

def mock_judge(claim: str, known_docs: List[str]) -> Tuple[str, str]:
    text = (claim or "").strip()
    if not text:
        return "insufficient", "empty_claim"
    if LOCAL.search(text) and known_docs:
        return "no", "local_with_known_docs"
    if LOCAL.search(text) and not EXT.search(text):
        return "no", "local_only"
    if EXT.search(text) and not known_docs:
        return "yes", "external_surface_no_docs"
    if EXT.search(text):
        return "yes", "external_surface"
    return "no", "mock_default_no"

def live_judge(claim: str, known_docs: List[str]) -> Tuple[str, str]:
    state = f"CLAIM:\n{claim[:2500]}\n\nKNOWN_DOCS:\n" + "\n".join(known_docs[:20])
    try:
        choice, conf, mid = decide_openrouter(
            state=state,
            question_name="research_needed",
            instructions="Does the agent need to read external/version-pinned official docs before coding this claim?",
            criteria={
                "yes": "touches external APIs, upstream semantics, version bumps, or undocumented surfaces",
                "no": "purely local in-repo change with enough known docs/fixtures",
                "insufficient": "claim too thin to decide — use #14 checklist fallback",
            },
        )
    except Exception as e:
        return "insufficient", f"live_error_{type(e).__name__}_use_checklist14"
    if choice not in ("yes", "no", "insufficient"):
        choice = "insufficient"
    return choice, f"live_{mid}_c{conf:.2f}"

def judge(claim: str, known_docs: List[str], mode: str) -> Tuple[str, str]:
    if mode == "mock":
        return mock_judge(claim, known_docs)
    if mode == "openrouter":
        if not env_live_enabled():
            return "insufficient", "live_not_enabled_use_checklist14"
        return live_judge(claim, known_docs)
    return "insufficient", f"unknown_judge_{mode}"

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--claim", default="")
    ap.add_argument("--issue-ref", default="")
    ap.add_argument("--known-docs-json", default="[]")
    ap.add_argument("--judge", choices=["mock", "openrouter"], default="mock")
    ap.add_argument("--session-id", default=None)
    ap.add_argument("--ops-db", default=None)
    ap.add_argument("--log", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    gold = fid = None
    known: List[str] = []
    issue_ref = args.issue_ref
    claim = args.claim
    if args.fixture:
        fx = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        claim = fx.get("claim_text") or ""
        known = list(fx.get("known_docs") or [])
        issue_ref = fx.get("issue_ref") or ""
        gold, fid = fx.get("gold_decision"), fx.get("id")
    else:
        known = json.loads(args.known_docs_json)
    decision, reason = judge(claim, known, args.judge)
    result = {"decision": decision, "reason_code": reason, "judge": args.judge,
              "gate_kind": "research", "fixture_id": fid, "gold_decision": gold,
              "fallback": "#14 checklist if insufficient/error"}
    dbp = Path(args.ops_db) if args.ops_db else None
    try:
        append_issue_snapshot(issue_ref=issue_ref or (fid or "unknown"), claim_text=claim,
                              session_id=args.session_id, meta={"fixture_id": fid}, db_path=dbp)
        append_gate_event(gate_kind="research", decision=decision, reason_code=reason,
                          tool_name="claim_snapshot", judge=args.judge, notes=claim[:200],
                          session_id=args.session_id, payload={"issue_ref": issue_ref, "fixture_id": fid},
                          db_path=dbp)
    except Exception as _ops_err:
        result["ops_db_error"] = type(_ops_err).__name__
    if args.log:
        p = Path(args.log); p.parent.mkdir(parents=True, exist_ok=True)
        import datetime as dt
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**result, "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}) + "\n")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{decision}\t{reason}")
    return 0 if decision == "no" else (2 if decision == "yes" else 3)

if __name__ == "__main__":
    raise SystemExit(main())
