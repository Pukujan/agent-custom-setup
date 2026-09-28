#!/usr/bin/env python3
"""Fast ACS vs auto-mode compare. Caps packs; parallel Jev; appends HTML."""
from __future__ import annotations
import argparse, json, os, statistics, sys, time
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
from harvest_packs import harvest_session_jsonl, harvest_many  # noqa: E402


def _percentile(vals: List[float], p: float) -> float | None:
    if not vals:
        return None
    ordered = sorted(vals)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return round(ordered[f], 1)
    return round(ordered[f] + (ordered[c] - ordered[f]) * (k - f), 1)


def load_packs(cap: int) -> List[Dict[str, Any]]:
    packs: List[Dict[str, Any]] = []
    # Fish fixtures
    fish = (
        Path(__file__).resolve().parents[2]
        / "jev-gate-pin"
        / "v0.1.0"
        / "fixtures"
        / "fish_hosted_vs_selfhost"
    )
    for p in sorted(fish.glob("*.json")):
        packs.append(json.loads(p.read_text(encoding="utf-8")))
    # Local tool packs + hard-deny + research
    for sub in ("tool_packs", "hard_deny", "research_packs"):
        d = ROOT / "fixtures" / sub
        if d.exists():
            for p in sorted(d.glob("*.json")):
                packs.append(json.loads(p.read_text(encoding="utf-8")))
    # Harvest session-ops synthetic (raise cap so corpus can reach 50–60)
    synth = (
        Path(__file__).resolve().parents[2]
        / "session-ops-capture"
        / "v0.1.0"
        / "tests"
        / "fixtures"
        / "synthetic_30_tools.jsonl"
    )
    if synth.exists():
        packs.extend(harvest_session_jsonl(synth, cap=min(30, cap)))
    sample = synth.parent / "sample_session.jsonl" if synth.exists() else None
    if sample and sample.exists():
        packs.extend(harvest_session_jsonl(sample, cap=min(10, cap)))
    # Pre-harvested Claude transcripts
    harvested = ROOT / "fixtures" / "harvested" / "packs.json"
    if harvested.exists():
        packs.extend(json.loads(harvested.read_text(encoding="utf-8")))
    # Live Claude home (optional fill) — only when still short of cap
    if len({(pk.get("id") or json.dumps(pk, sort_keys=True)[:80]) for pk in packs}) < cap:
        claude = Path.home() / ".claude" / "projects"
        if claude.exists():
            packs.extend(harvest_many([claude], cap=cap, per_file=8))
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
    ap.add_argument("--cap", type=int, default=60)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--live", action="store_true", help="or set ACS_JEV_LIVE=1")
    ap.add_argument("--append-html", action="store_true")
    ap.add_argument("--out-json", default=str(ROOT / "reports" / "runs" / "latest.json"))
    args = ap.parse_args(argv)
    live = args.live or os.environ.get("ACS_JEV_LIVE", "").strip().lower() in ("1", "true", "yes")
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
    jev_lat = [float(r["jev_ms"]) for r in rows if r.get("jev_ms")]
    acs_lat = [float(r["acs_ms"]) for r in rows if r.get("acs_ms") is not None]
    n = len(rows)
    agree = sum(1 for r in rows if r["agree"])
    disagree = n - agree
    summary = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_packs": n,
        "live": live,
        "agree": agree,
        "disagree": disagree,
        "agree_pct": round(100.0 * agree / n, 1) if n else 0.0,
        "fn_vs_gold": sum(r["fn"] for r in rows),
        "fp_vs_gold": sum(r["fp"] for r in rows),
        "wall_ms": round(wall, 1),
        "median_jev_ms": round(statistics.median(jev_lat), 1) if jev_lat else None,
        "p50_jev_ms": _percentile(jev_lat, 50),
        "p95_jev_ms": _percentile(jev_lat, 95),
        "p50_acs_ms": _percentile(acs_lat, 50),
        "p95_acs_ms": _percentile(acs_lat, 95),
        "workers": args.workers,
        "model": os.environ.get("ACS_JEV_MODEL") or "typesafe/jev-1.13",
        "notes": (
            "Transcript replay from Claude JSONL harvest + session-ops fixtures + Fish/hard-deny packs. "
            "Hard-deny peer never sends catastrophic rm to Jev. Fast Jev (typesafe/jev-1.13) OK."
        ),
    }
    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "rows": rows}
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (out.parent / f"{run_id}.json").write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
    if args.append_html:
        append_run(ROOT / "reports" / "jev-oss-compare.html", summary, rows)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
