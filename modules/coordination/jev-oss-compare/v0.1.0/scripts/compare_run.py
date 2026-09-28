#!/usr/bin/env python3
"""Fast ACS vs auto-mode compare. Caps packs; parallel Jev; appends HTML."""
from __future__ import annotations
import argparse, json, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from acs_lane import run_acs_pack  # noqa: E402
from auto_mode_lane import run_auto_mode_pack  # noqa: E402
from html_report import append_run  # noqa: E402
from harvest_packs import harvest_session_jsonl  # noqa: E402

def load_packs(cap: int) -> List[Dict[str, Any]]:
    packs: List[Dict[str, Any]] = []
    # Fish fixtures
    fish = Path(__file__).resolve().parents[2] / "jev-gate-pin" / "v0.1.0" / "fixtures" / "fish_hosted_vs_selfhost"
    for p in sorted(fish.glob("*.json")):
        packs.append(json.loads(p.read_text(encoding="utf-8")))
    # Local tool packs
    for p in sorted((ROOT / "fixtures" / "tool_packs").glob("*.json")):
        packs.append(json.loads(p.read_text(encoding="utf-8")))
    for p in sorted((ROOT / "fixtures" / "hard_deny").glob("*.json")):
        packs.append(json.loads(p.read_text(encoding="utf-8")))
    # Harvest session-ops synthetic
    synth = Path(__file__).resolve().parents[2] / "session-ops-capture" / "v0.1.0" / "tests" / "fixtures" / "synthetic_30_tools.jsonl"
    if synth.exists():
        packs.extend(harvest_session_jsonl(synth, cap=min(8, cap)))
    harvested = ROOT / "fixtures" / "harvested" / "packs.json"
    if harvested.exists():
        packs.extend(json.loads(harvested.read_text(encoding="utf-8")))
    # Dedupe by id
    seen, out = set(), []
    for pk in packs:
        i = pk.get("id") or json.dumps(pk, sort_keys=True)[:80]
        if i in seen:
            continue
        seen.add(i)
        pk["id"] = i
        out.append(pk)
        if len(out) >= cap:
            break
    return out

def _one(pack: Dict[str, Any], live: bool) -> Dict[str, Any]:
    acs = run_acs_pack(pack, use_live=live)
    auto = run_auto_mode_pack(pack, use_live=live)
    gold = pack.get("gold_decision")
    agree = acs["decision"] == auto["decision"]
    fn = fp = 0
    if gold in ("deny", "block"):
        if acs["decision"] != "deny":
            fn += 1
    if gold == "allow" and acs["decision"] == "deny":
        fp += 1
    return {
        "id": pack.get("id"),
        "gold": gold,
        "acs_decision": acs["decision"],
        "acs_layer": acs["layer"],
        "acs_ms": acs["latency_ms"],
        "auto_decision": auto["decision"],
        "auto_layer": auto["layer"],
        "auto_ms": auto["latency_ms"],
        "jev_ms": round(max(acs.get("jev_ms") or 0, auto.get("jev_ms") or 0), 2),
        "agree": agree,
        "fn": fn,
        "fp": fp,
        "acs": acs,
        "auto": auto,
    }

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=12)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--live", action="store_true", help="or set ACS_JEV_LIVE=1")
    ap.add_argument("--append-html", action="store_true")
    ap.add_argument("--out-json", default=str(ROOT / "reports" / "runs" / "latest.json"))
    args = ap.parse_args(argv)
    live = args.live or __import__("os").environ.get("ACS_JEV_LIVE", "").strip() in ("1", "true", "yes")
    packs = load_packs(args.cap)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    t0 = time.perf_counter()
    rows: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = [ex.submit(_one, p, live) for p in packs]
        for f in as_completed(futs):
            rows.append(f.result())
    rows.sort(key=lambda r: str(r.get("id")))
    wall = (time.perf_counter() - t0) * 1000
    jev_lat = [r["jev_ms"] for r in rows if r.get("jev_ms")]
    summary = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_packs": len(rows),
        "live": live,
        "agree": sum(1 for r in rows if r["agree"]),
        "disagree": sum(1 for r in rows if not r["agree"]),
        "fn_vs_gold": sum(r["fn"] for r in rows),
        "fp_vs_gold": sum(r["fp"] for r in rows),
        "wall_ms": round(wall, 1),
        "median_jev_ms": round(statistics.median(jev_lat), 1) if jev_lat else None,
        "workers": args.workers,
        "notes": "Transcript replay from session-ops synthetic + Fish fixtures. Hard-deny peer never sends catastrophic rm to Jev.",
    }
    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n", encoding="utf-8")
    # also stamp run id file
    (out.parent / f"{run_id}.json").write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
    if args.append_html:
        append_run(ROOT / "reports" / "jev-oss-compare.html", summary, rows)
    print(json.dumps(summary, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
