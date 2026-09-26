#!/usr/bin/env python3
"""Aggregate evals/results/run_*.json and apply frozen expectation rules (v3).

- current/stub: every recorded arm must satisfy its rule.
- metamorphic_invariance: per-task pass-fraction ≥0.5 (majority over ≥3 arms)
  must equal the same majority pass-set as the "against" variant.
- metamorphic_degrades: T3 fails on EVERY recorded arm (strict; 2/2 passed v1).
Exit 0 only if all expectations hold. No LLM involved.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = json.loads((ROOT / "evals" / "reader_tasks.json").read_text(encoding="utf-8"))
RESULTS = sorted((ROOT / "evals" / "results").glob("run_*.json"))
TASK_IDS = [t["id"] for t in KEY["tasks"]]
MIN_ARMS = {"reordered": 3, "bold_stripped": 3}


def variant_arms(records, variant):
    """List of per-arm {task_id: bool} dicts."""
    out = []
    for r in records:
        if r["variant"] != variant:
            continue
        for entry in r["runs"]:
            out.append({tid: bool(entry["tasks"].get(tid, {}).get("pass")) for tid in TASK_IDS})
    return out


def majority_set(arms):
    """{task: True/False} by ≥0.5; None when no arms."""
    if not arms:
        return None
    return {tid: sum(1 for a in arms if a[tid]) / len(arms) >= 0.5 for tid in TASK_IDS}


def main() -> int:
    records = [json.loads(p.read_text()) for p in RESULTS]
    failures, lines = [], []
    for variant, rule in KEY["expectations"].items():
        arms = variant_arms(records, variant)
        mode = rule["mode"]
        if not arms:
            lines.append(f"{variant:16s} MISSING")
            failures.append(f"{variant}: no results")
            continue
        minm = MIN_ARMS.get(variant, 1)
        if len(arms) < minm:
            failures.append(f"{variant}: {len(arms)} arms < required {minm}")
        if mode == "must_pass":
            bad = [f"arm{i+1}:{tid}" for i, a in enumerate(arms) for tid in rule["tasks"] if not a.get(tid)]
            verdict = f"{len(arms)} arms PASS" if not bad else "FAIL " + ",".join(bad)
            failures.extend(f"{variant}: {b}" for b in bad)
        elif mode == "record_differential":
            cur = variant_arms(records, "current")
            cs = sum(sum(a.values()) for a in cur) / max(len(cur), 1)
            vs = sum(sum(a.values()) for a in arms) / max(len(arms), 1)
            if cs < vs:
                failures.append(f"{variant}: current regressed below baseline ({cs:.1f} < {vs:.1f})")
            verdict = f"obs: current={cs:.1f}/{len(TASK_IDS)} ({len(cur)} arms) vs {variant}={vs:.1f}/{len(TASK_IDS)} ({len(arms)} arms)" + (" REGRESSION" if cs < vs else "")
        elif mode == "metamorphic_invariance":
            base = majority_set(variant_arms(records, rule["against"]))
            mine = majority_set(arms)
            if mine == base:
                verdict = f"PASS majority={sorted(k for k, v in mine.items() if v)} ({len(arms)} arms)"
            else:
                verdict = f"FAIL variant-majority={mine} vs {rule['against']}-majority={base}"
                failures.append(f"{variant}: {verdict}")
        elif mode == "metamorphic_degrades":
            tfails = [i + 1 for i, a in enumerate(arms) if not a["T3"]]
            if tfails and len(tfails) == len(arms):
                verdict = f"PASS T3-fail on all {len(arms)} arms"
            elif tfails:
                verdict = f"PARTIAL T3-fail arms={tfails}/{len(arms)} (strict rule: all)"
                failures.append(f"{variant}: degradation incomplete ({tfails}/{len(arms)})")
            else:
                verdict = "FAIL no arm degraded"
                failures.append(f"{variant}: {verdict}")
        else:
            verdict = f"UNKNOWN MODE {mode}"
            failures.append(f"{variant}: {verdict}")
        lines.append(f"{variant:16s} {verdict}")
    for l in lines:
        print(l)
    print("HOLDOUT: not_run (no sealed private fixture / independent evaluator — evals/README.md)")
    if failures:
        print("SUITE: FAIL")
        for f in failures:
            print(" -", f)
        return 1
    print("SUITE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
