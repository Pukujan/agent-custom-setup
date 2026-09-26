#!/usr/bin/env python3
"""Reader-task arm runner for ACS-0003 (owner direction: omp CLI sessions).

Each arm = one fresh headless `omp -p` session given ONLY the variant README +
one frozen task prompt; it must answer JSON. Isolation (v2, after disclosed
v1-v3 confound): --no-tools --no-session --no-rules --no-extensions --no-skills
plus an overlay disabling the ambient advisor runtime. Grading = deterministic
anchor matching from evals/reader_tasks.json (no LLM judge). Emits
evals/results/run_<id>.json (full answers + sha256 + flags for re-gradation).

Per CGM docs/README_QUALITY_TDD.md: reader tasks + metamorphic + differential;
holdout label stays not_run (no sealed fixture).
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = json.loads((ROOT / "evals" / "reader_tasks.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "evals" / "results"
RESULTS.mkdir(exist_ok=True)

ARM_FLAGS = ["-p", "--no-tools", "--no-session", "--no-rules", "--no-extensions", "--no-skills"]
OVERLAY = ROOT / "evals" / "omp-arms-overlay.yml"  # committed; advisor: enabled: false


def run_omp_arm(prompt: str, model: str, max_time: int = 120, retries: int = 2) -> tuple[str, str]:
    """Invoke one isolated omp session; return (raw stdout, error|'')."""
    if not OVERLAY.is_file():
        raise SystemExit(f"FATAL: isolation overlay missing: {OVERLAY} (refusing advisor-on run)")
    cmd = ["omp", *ARM_FLAGS, "--config", str(OVERLAY)]
    proc = None
    for attempt in range(retries + 1):
        proc = subprocess.run(cmd + ["--max-time", str(max_time), "--model", model, prompt],
                              capture_output=True, text=True)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout, ""
        time.sleep(3 * (attempt + 1))
    return (proc.stdout if proc else ""), f"exit={proc.returncode if proc else 'n/a'} err={proc.stderr[-400:] if proc else ''}"


def parse_answer(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {}
    try:
        v = json.loads(m.group(0))
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        return {}


def grade(task: dict, answer: dict) -> tuple[bool, list]:
    reasons = []
    ok = True
    for field, spec in task["fields"].items():
        text = str(answer.get(field, "")).lower()
        if not any(a.lower() in text for a in spec["any"]):
            ok = False
            reasons.append(f"{field}: no anchor match in {text[:80]!r}")
    blob = " ".join(str(v) for v in answer.values()).lower()
    for forb in task.get("forbidden_any", []):
        if forb.lower() in blob:
            ok = False
            reasons.append(f"forbidden {forb!r} present")
    return ok, reasons


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--runs", type=int, default=None)
    ap.add_argument("--models", default=",".join(KEY["models"]))
    args = ap.parse_args()
    rpv = KEY["runs_per_variant"]
    runs = args.runs if args.runs is not None else (rpv.get(args.variant, 2) if isinstance(rpv, dict) else rpv)

    vpath = ROOT / "evals" / "variants" / f"{args.variant}.md"
    readme = vpath.read_text(encoding="utf-8")
    run_id = f"{args.variant}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    ver = subprocess.run(["omp", "--version"], capture_output=True, text=True)
    omp_version = ((ver.stdout or "") + (ver.stderr or "")).strip().splitlines()
    omp_version = omp_version[0] if omp_version else "unknown"
    flags = ARM_FLAGS + (["--config", str(OVERLAY)] if OVERLAY.is_file() else [])
    record = {
        "schema": "acs-0003.arm-run.v2", "run_id": run_id, "variant": args.variant,
        "cgm_pinned": KEY["pinned_helper"],
        "key_schema": KEY["schema"], "key_note_head": KEY["revision_note"].split(" ")[0],
        "readme_sha256": hashlib.sha256(readme.encode()).hexdigest(),
        "arm_flags": flags, "omp_version": omp_version,
        "advisor_enabled_during_run": not OVERLAY.is_file(),
        "started_at": datetime.now(timezone.utc).isoformat(), "runs": [],
    }
    for model in args.models.split(","):
        for n in range(1, runs + 1):
            entry = {"run": n, "model": model, "tasks": {}}
            for task in KEY["tasks"]:
                prompt = (
                    "Read the README below. Answer ONLY with a JSON object matching "
                    f"the keys in this task. Task {task['id']}: {task['prompt']}\n\n"
                    "--- README BEGIN ---\n" + readme + "\n--- README END ---\n"
                )
                raw, err = run_omp_arm(prompt, model)
                ans = parse_answer(raw)
                ok, reasons = grade(task, ans) if ans else (False, ["unparseable"])
                entry["tasks"][task["id"]] = {
                    "pass": ok, "reasons": reasons,
                    "answer": {k: str(ans.get(k, ""))[:200] for k in task["fields"]},
                    "answer_full": {k: str(ans.get(k, "")) for k in task["fields"]},
                    "error": err,
                }
                print(f"{args.variant} {model} run{n} {task['id']}: {'PASS' if ok else 'FAIL'} "
                      f"{'; '.join(reasons)[:110]}", flush=True)
            record["runs"].append(entry)
    (RESULTS / f"run_{run_id}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    print(f"wrote evals/results/run_{run_id}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
