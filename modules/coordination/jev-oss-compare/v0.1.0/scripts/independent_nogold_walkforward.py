#!/usr/bin/env python3
"""Independent-stream no-gold multi-lane walk-forward (ACS TX | Claude TX).

Alex lock: ACS and Claude are SEPARATE sequential walk-forwards (never interleaved).
gold=false: pairwise lane agree matrix, verdict counts, blind deny/escalate lists.
Machine-parse tool events only. Live Jev when ACS_JEV_LIVE=1. Append existing HTML.
Never prints secrets. Never touches main.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PIN_SCRIPTS = HERE.parents[2] / "jev-gate-pin" / "v0.1.0" / "scripts"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PIN_SCRIPTS))

from harvest_packs import redact  # noqa: E402
from pin_extract import extract_pins  # noqa: E402
from gather import build_package  # noqa: E402
from gate import mock_judge  # noqa: E402
import acs_lane  # noqa: E402
import auto_mode_lane  # noqa: E402
import jev_decide  # noqa: E402
import html_report  # noqa: E402
import auto_mode_policy as pol  # noqa: E402
import multi_lane_walkforward as mlw  # noqa: E402

LANE_IDS = ["L1_acs", "L2_auto", "L3_pi", "L4_all_jev", "L5_compaction"]


def _load_dotenv(paths: List[Path]) -> None:
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=r"D:\claude\agent-custom-setup",
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def load_events(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    rows.sort(key=lambda r: (str(r.get("when") or ""), str(r.get("id") or "")))
    return rows


class RollingPins:
    def __init__(self) -> None:
        self.pins: List[str] = [
            "NEVER commit main without Alex ask",
            "gold=false: pairwise lane agree NOT agree-with-gold",
            "ONLY API = live Jev Decisions",
            "append EXISTING jev-oss-compare.html only",
            "ACS TX and Claude TX independent (no interleave)",
        ]

    def observe_tool(self, tool: Dict[str, Any]) -> None:
        """Machine-extract hard pins from past tool args only (no LLM labeling)."""
        text = f"{tool.get('name') or ''} {tool.get('args_summary') or ''}"
        for m in re.finditer(r"(?i)\b(MUST(?:\s+NOT)?|NEVER|ONLY)\b[^\n.!?]{0,120}", text):
            pin = " ".join(m.group(0).split())
            if pin and pin not in self.pins:
                self.pins.append(pin)
        # keep bounded
        if len(self.pins) > 64:
            self.pins = self.pins[:8] + self.pins[-56:]

    def brief(self) -> str:
        return "ACS independent walk-forward pins:\n- " + "\n- ".join(self.pins[-24:])


def enrich_pack(ev: Dict[str, Any], pins: RollingPins) -> Dict[str, Any]:
    pack = dict(ev)
    pack["brief"] = pins.brief()
    pack["corrections"] = list(pins.pins[-16:])
    pack["gold_decision"] = None  # force no gold
    pack["gold"] = False
    return pack


def run_pack(pack: Dict[str, Any], *, live: bool) -> Dict[str, Any]:
    # reuse lane runners from mlw; strip gold scoring
    out = mlw.run_pack_all_lanes(pack, live=live)
    out["gold"] = None
    out["gold_false"] = True
    # clear agree/fn/fp gold fields; keep decisions
    for lid, st in (out.get("lanes") or {}).items():
        st["agree"] = None
        st["fn"] = 0
        st["fp"] = 0
    return out


def pairwise_matrix(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    pairs = list(combinations(LANE_IDS, 2))
    mat: Dict[str, Any] = {"pairs": {}, "n": len(rows)}
    for a, b in pairs:
        same = 0
        scored = 0
        for r in rows:
            da = ((r.get("lanes") or {}).get(a) or {}).get("decision")
            db = ((r.get("lanes") or {}).get(b) or {}).get("decision")
            if not da or not db:
                continue
            scored += 1
            if da == db:
                same += 1
        mat["pairs"][f"{a}__{b}"] = {
            "same": same,
            "scored": scored,
            "agree_pct": round(100.0 * same / scored, 1) if scored else None,
        }
    return mat


def verdict_counts(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for lid in LANE_IDS:
        c = {"allow": 0, "deny": 0, "escalate": 0, "other": 0}
        for r in rows:
            d = ((r.get("lanes") or {}).get(lid) or {}).get("decision") or "other"
            if d in c:
                c[d] += 1
            else:
                c["other"] += 1
        out[lid] = c
    return out


def blind_lists(rows: List[Dict[str, Any]], *, limit: int = 80) -> Dict[str, Any]:
    """Blind deny/escalate catches: events where any lane denies or escalates (no gold)."""
    deny_hits: List[Dict[str, Any]] = []
    esc_hits: List[Dict[str, Any]] = []
    for r in rows:
        lanes = r.get("lanes") or {}
        deniers = [lid for lid, st in lanes.items() if st.get("decision") == "deny"]
        escers = [lid for lid, st in lanes.items() if st.get("decision") == "escalate"]
        tool = r.get("text") or ""
        base = {"id": r.get("id"), "tool": tool[:240], "when": r.get("when")}
        if deniers:
            deny_hits.append({**base, "lanes": deniers})
        if escers:
            esc_hits.append({**base, "lanes": escers})
    return {
        "deny_n": len(deny_hits),
        "escalate_n": len(esc_hits),
        "deny_sample": deny_hits[:limit],
        "escalate_sample": esc_hits[:limit],
    }


def summarize_stream(
    rows: List[Dict[str, Any]],
    *,
    stream: str,
    live: bool,
    run_id: str,
    wall_ms: float,
    workers: int,
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    per_lane: Dict[str, Any] = {}
    for lid in LANE_IDS:
        jevs = [
            float((r.get("lanes") or {}).get(lid, {}).get("jev_ms") or 0)
            for r in rows
            if (r.get("lanes") or {}).get(lid)
        ]
        vc = verdict_counts(rows).get(lid) or {}
        per_lane[lid] = {
            "n": len(rows),
            "allow": vc.get("allow", 0),
            "deny": vc.get("deny", 0),
            "escalate": vc.get("escalate", 0),
            "p50_jev_ms": round(statistics.median(jevs), 1) if jevs else None,
        }
    return {
        "run_id": run_id,
        "kind": "independent_nogold_walkforward",
        "gold": False,
        "stream": stream,
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "live": live,
        "sha": git_sha(),
        "n_events": len(rows),
        "per_lane": per_lane,
        "pairwise": pairwise_matrix(rows),
        "verdicts": verdict_counts(rows),
        "blind": blind_lists(rows),
        "wall_ms": round(wall_ms, 1),
        "workers": workers,
        "model": os.environ.get("ACS_JEV_MODEL") or "typesafe/jev-1.13",
        "meta": meta,
        "notes": (
            f"Independent no-gold walk-forward stream={stream}. "
            "Pairwise lane agree + verdict counts + blind deny/escalate. "
            "Not agree-with-gold. Append existing compare HTML only."
        ),
    }


def append_html_stream(summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> Path:
    report = ROOT / "reports" / "jev-oss-compare.html"
    rid = summary["run_id"]
    stream = summary.get("stream")
    # flat rows for existing append_run (acs vs auto peer)
    flat = []
    for r in rows:
        l1 = (r.get("lanes") or {}).get("L1_acs") or {}
        l2 = (r.get("lanes") or {}).get("L2_auto") or {}
        flat.append(
            {
                "id": r.get("id"),
                "gold": None,
                "acs_decision": l1.get("decision"),
                "acs_layer": l1.get("layer"),
                "acs_ms": (r.get("raw") or {}).get("L1_acs", {}).get("latency_ms"),
                "auto_decision": l2.get("decision"),
                "auto_layer": l2.get("layer"),
                "auto_ms": (r.get("raw") or {}).get("L2_auto", {}).get("latency_ms"),
                "jev_ms": max(float(l1.get("jev_ms") or 0), float(l2.get("jev_ms") or 0)),
                "agree": l1.get("decision") == l2.get("decision"),
                "fn": 0,
                "fp": 0,
            }
        )
    summary_for_html = {
        **summary,
        "agree": sum(1 for r in flat if r.get("agree")),
        "disagree": sum(1 for r in flat if not r.get("agree")),
        "agree_pct": None,
        "fn_vs_gold": 0,
        "fp_vs_gold": 0,
        "n_packs": summary.get("n_events"),
        "notes": summary.get("notes") + " | pairwise=" + json.dumps(summary.get("pairwise")),
    }
    html_report.append_run(report, summary_for_html, flat)

    # inject plain-English independent stream block
    lines = [
        f'<section class="run" data-run-id="{rid}-nogold" id="run-{rid}-nogold">',
        f"<h3>Independent no-gold walk-forward — {html_report._esc(stream)} — {rid}</h3>",
        f"<p><strong>gold=false</strong>. Stream <code>{html_report._esc(stream)}</code> alone "
        f"(not interleaved). n=<strong>{summary.get('n_events')}</strong> tool events. "
        "Metrics: pairwise lane agree, verdict counts, blind deny/escalate lists.</p>",
        "<h4>Verdict counts</h4><table class='table table-dark table-sm'><thead><tr>"
        "<th>Lane</th><th>allow</th><th>deny</th><th>escalate</th><th>Jev p50</th></tr></thead><tbody>",
    ]
    for lid, st in (summary.get("per_lane") or {}).items():
        lines.append(
            f"<tr><td>{lid}</td><td>{st.get('allow')}</td><td>{st.get('deny')}</td>"
            f"<td>{st.get('escalate')}</td><td>{st.get('p50_jev_ms')}</td></tr>"
        )
    lines.append("</tbody></table>")
    lines.append("<h4>Pairwise lane agree %</h4><ul>")
    for k, v in ((summary.get("pairwise") or {}).get("pairs") or {}).items():
        lines.append(f"<li><code>{html_report._esc(k)}</code>: {v.get('agree_pct')}% ({v.get('same')}/{v.get('scored')})</li>")
    lines.append("</ul>")
    blind = summary.get("blind") or {}
    lines.append(
        f"<p><strong>Blind catches</strong>: deny_n={blind.get('deny_n')} escalate_n={blind.get('escalate_n')}</p>"
    )
    lines.append("<h4>Blind deny sample</h4><ul>")
    for h in (blind.get("deny_sample") or [])[:25]:
        lines.append(
            f"<li><code>{html_report._esc(h.get('id'))}</code> lanes={html_report._esc(','.join(h.get('lanes') or []))} "
            f"{html_report._esc(h.get('tool'))}</li>"
        )
    lines.append("</ul><h4>Blind escalate sample</h4><ul>")
    for h in (blind.get("escalate_sample") or [])[:25]:
        lines.append(
            f"<li><code>{html_report._esc(h.get('id'))}</code> lanes={html_report._esc(','.join(h.get('lanes') or []))} "
            f"{html_report._esc(h.get('tool'))}</li>"
        )
    lines.append("</ul></section>\n")
    text = report.read_text(encoding="utf-8")
    block = "\n".join(lines)
    if "<!--RUNS-->" in text:
        text = text.replace("<!--RUNS-->", "<!--RUNS-->\n" + block, 1)
    else:
        text += block
    report.write_text(text, encoding="utf-8")
    return report


def walk_stream(
    events: List[Dict[str, Any]],
    *,
    live: bool,
    workers: int,
    stream: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    pins = RollingPins()
    packs: List[Dict[str, Any]] = []
    for ev in events:
        pack = enrich_pack(ev, pins)
        packs.append(pack)
        # update pins AFTER packing this step (past-only for next)
        pins.observe_tool(pack.get("proposed_tool") or {})

    run_id = datetime.now(timezone.utc).strftime(f"mlwf-ind-{stream}-%Y%m%dT%H%M%SZ")
    print(f"start run_id={run_id} stream={stream} live={live} n={len(packs)} workers={workers}", flush=True)
    t0 = time.perf_counter()
    rows: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(run_pack, p, live=live): p for p in packs}
        done = 0
        for fut in as_completed(futs):
            rows.append(fut.result())
            done += 1
            if done % 25 == 0 or done == len(packs):
                print(f"progress {stream} {done}/{len(packs)}", flush=True)
    rows.sort(key=lambda r: (str(r.get("when") or ""), str(r.get("id") or "")))
    wall = (time.perf_counter() - t0) * 1000
    meta = {"n_in": len(events), "n_pins": len(pins.pins), "pins_tail": pins.pins[-12:], "gold": False}
    summary = summarize_stream(rows, stream=stream, live=live, run_id=run_id, wall_ms=wall, workers=workers, meta=meta)
    return rows, summary


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", choices=["acs", "claude"], required=True)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--append-html", action="store_true")
    ap.add_argument("--chunk", type=int, default=0, help="If >0, only first N events")
    ap.add_argument("--offset", type=int, default=0, help="Skip first N events")
    args = ap.parse_args(argv)

    _load_dotenv(
        [
            Path(r"D:\claude\agent-custom-setup\.env"),
            Path(r"C:\Users\pujan\OneDrive\Desktop\configs\.env"),
        ]
    )
    if args.live:
        os.environ["ACS_JEV_LIVE"] = "1"
    live = bool(args.live and jev_decide.live_enabled() and jev_decide._key())

    if args.stream == "acs":
        path = ROOT / "fixtures" / "acs_tx" / "tools.jsonl"
        stream_name = "acs_tx"
    else:
        path = ROOT / "fixtures" / "claude_tx" / "tools.jsonl"
        stream_name = "claude_tx"

    events = load_events(path)
    if args.offset:
        events = events[args.offset :]
    if args.chunk and args.chunk > 0:
        events = events[: args.chunk]

    rows, summary = walk_stream(events, live=live, workers=args.workers, stream=stream_name)

    runs = ROOT / "reports" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "rows": rows}
    out = runs / f"{summary['run_id']}.json"
    # rows can be huge; still write full for evidence
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    latest = runs / f"independent-nogold-{args.stream}-latest.json"
    # write summary-only latest for quick read
    latest.write_text(json.dumps({"summary": summary}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k not in ("meta",)}, indent=2), flush=True)

    if args.append_html:
        path_html = append_html_stream(summary, rows)
        print(f"appended_html={path_html}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
