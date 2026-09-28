#!/usr/bin/env python3
"""Optional post-run criteria stub shaped like TheoOliveira/pi-jev jev-gate.

NOT wired as live PreToolUse. Claude+Kilo keep ACS adapters for tool time.
Mock path for CI; live Jev when ACS_JEV_LIVE=1.
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(HERE))
import jev_decide  # noqa: E402

def mock_eval(state: str, criteria: str, threshold: float) -> dict:
    # Cheap lexical stand-in for CI.
    s = (state or "").lower()
    c = (criteria or "").lower()
    score = 0.85 if ("pass" in s or "ok" in s) and "fail" not in s else 0.4
    if "secret" in s or "sk-" in s:
        score = 0.1
    return {
        "passed": score >= threshold,
        "probability": score,
        "criteria": criteria,
        "threshold": threshold,
        "elapsed_ms": 0.2,
        "mode": "mock",
    }

def live_eval(state: str, criteria: str, threshold: float) -> dict:
    t0 = time.perf_counter()
    choice, conf, model, ms = jev_decide.decide_choice(
        state,
        "gate_passed",
        f'Does the provided output satisfy: "{criteria}"?',
        {
            "allow": "criteria satisfied (map to passed)",
            "deny": "criteria not satisfied",
            "escalate": "insufficient evidence",
        },
    )
    # Map choice→probability for threshold compare.
    prob = {"allow": max(conf, threshold), "deny": min(conf, threshold - 0.01), "escalate": threshold - 0.05}.get(choice, 0.0)
    return {
        "passed": choice == "allow" and prob >= threshold,
        "probability": prob,
        "confidence": conf,
        "criteria": criteria,
        "threshold": threshold,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        "jev_ms": round(ms, 2),
        "mode": "live",
        "model": model,
        "choice": choice,
    }

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Post-run jev-gate stub (not PreToolUse)")
    ap.add_argument("-c", "--criteria", required=True)
    ap.add_argument("-f", "--file", help="state file")
    ap.add_argument("--state", default="")
    ap.add_argument("-p", "--threshold", type=float, default=0.7)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    state = args.state
    if args.file:
        state = Path(args.file).read_text(encoding="utf-8")
    if args.live and jev_decide.live_enabled():
        result = live_eval(state, args.criteria, args.threshold)
    else:
        result = mock_eval(state, args.criteria, args.threshold)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(("PASS" if result["passed"] else "FAIL") + f"\t{result['probability']:.3f}")
    return 0 if result["passed"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
