#!/usr/bin/env python3
"""Aggregate run_*.json from ONE cohort directory (score.py --dir) and apply the
frozen expectation rules (key v3; majority invariance, strict M-04 degrade).

Pool hygiene: each directory must contain a single runner generation — v1
records carry truncated 200-char answers, v2/v2.1 carry answer_full; score.py
ERRORS if the selected directory mixes `schema` values, so cohorts can never be
silently double-counted. Exit 0 only if all expectations hold. No LLM involved.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = json.loads((ROOT / "evals" / "reader_tasks.json").read_text(encoding="utf-8"))
TASK_IDS = [t["id"] for t in KEY["tasks"]]
MIN_ARMS = {"reordered": 3, "bold_stripped": 3}


def variant_arms(records, variant):
    out = []
    for r in records:
        if r["variant"] != variant:
            continue
        for entry in r["runs"]:
            out.append({tid: bool(entry["tasks"].get(tid, {}).get("pass")) for tid in TASK_IDS})
    return out


def majority_set(arms):
    if not arms:
        return None
    return {tid: sum(1 for a in arms if a[tid]) / len(arms) >= 0.5 for tid in TASK_IDS}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="evals/results",
                    help="cohort directory relative to repo root (must be one runner generation)")
    args = ap.parse_args()
    paths = sorted((ROOT / args.dir).glob("run_*.json"))
    if not paths:
        print(f"NO RECORDS in {args.dir}")
        return 1
    records = [json.loads(p.read_text()) for p in paths]
    schemas = {r.get("schema", "?") for r in records}
    if len(schemas) > 1:
        print(f"MIXED COHORTS in {args.dir}: {sorted(schemas)} — refusing to pool")
        return 1
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
            verdict = (f"obs: current={cs:.1f}/{len(TASK_IDS)} ({len(cur)} arms) vs "
                       f"{variant}={vs:.1f}/{len(TASK_IDS)} ({len(arms)} arms)"
                       + (" REGRESSION" if cs < vs else ""))
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
