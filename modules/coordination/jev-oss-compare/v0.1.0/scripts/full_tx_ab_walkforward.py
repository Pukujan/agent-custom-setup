#!/usr/bin/env python3
"""Full-transcript dual-stream walk-forward with epistemic pin layer + Ablation A/B.

LOCKED (Alex):
- ACS Grok TX and Claude hades-v2 JSONL walked SEPARATELY (never interleaved).
- Each USER msg+ts: packer = this + ALL prior user msgs + pin statuses
  → live Jev pin-decide → epistemic exploring|soft|hard|superseded.
- Each TOOL: hard denylist (0 Jev) → else tiny pack active soft+hard → live Jev tool gate.
- Ablation A: epistemic pin store feeds L1 ACS only; L2-L5 see baseline pins.
- Ablation B: SAME epistemic pin layer in FRONT of ALL lanes L1-L5.
- ACS_JEV_LIVE=1 typesafe/jev-1.13 uncapped. Append existing dark HTML. Never main.
"""
from __future__ import annotations

import argparse
import hashlib
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
from gather import build_package  # noqa: E402
from gate import mock_judge  # noqa: E402
import acs_lane  # noqa: E402
import auto_mode_lane  # noqa: E402
import jev_decide  # noqa: E402
import html_report  # noqa: E402
import auto_mode_policy as pol  # noqa: E402
import multi_lane_walkforward as mlw  # noqa: E402

LANE_IDS = ["L1_acs", "L2_auto", "L3_pi", "L4_all_jev", "L5_compaction"]
EPISTEMIC = ("exploring", "soft", "hard", "superseded")


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


def git_sha(cwd: Optional[Path] = None) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd or ROOT.parents[3]),
            text=True,
        ).strip()
    except Exception:
        return "unknown"


# ---------- Epistemic pin store ----------

class EpistemicPinStore:
    """Living pin store with epistemic statuses from live Jev user classify."""

    def __init__(self, seed: Optional[List[Dict[str, Any]]] = None) -> None:
        self.pins: List[Dict[str, Any]] = list(seed or [])
        # seed baseline hard locks
        if not self.pins:
            for text in (
                "NEVER commit main without Alex ask",
                "ONLY API = live Jev Decisions",
                "append EXISTING jev-oss-compare.html only",
                "ACS TX and Claude TX independent (no interleave)",
                "Human intent ≠ agent data claims",
            ):
                self.pins.append(
                    {
                        "id": "seed-" + hashlib.sha1(text.encode()).hexdigest()[:8],
                        "text": text,
                        "status": "hard",
                        "when": "seed",
                        "corr": None,
                        "supersedes": None,
                    }
                )

    def statuses_brief(self) -> str:
        lines = []
        for p in self.pins[-48:]:
            lines.append(f"[{p.get('status')}] {p.get('text')}")
        return "\n".join(lines)

    def active_soft_hard(self) -> List[str]:
        out = []
        for p in self.pins:
            if p.get("status") in ("soft", "hard"):
                out.append(str(p.get("text") or ""))
        return [x for x in out if x]

    def baseline_only(self) -> List[str]:
        return [str(p.get("text") or "") for p in self.pins if str(p.get("id") or "").startswith("seed-")]

    def apply_decision(
        self,
        *,
        user_id: str,
        user_text: str,
        when: str,
        status: str,
        pin_text: str,
        corr: Optional[str] = None,
        supersedes: Optional[str] = None,
    ) -> Dict[str, Any]:
        status = status if status in EPISTEMIC else "exploring"
        # supersede prior
        if supersedes or status == "superseded":
            target = (supersedes or pin_text or user_text or "").lower()
            for p in self.pins:
                if target and (target in (p.get("text") or "").lower() or (p.get("id") == supersedes)):
                    p["status"] = "superseded"
        entry = {
            "id": f"pin-{user_id}",
            "text": (pin_text or user_text or "")[:400],
            "status": status,
            "when": when,
            "corr": corr,
            "supersedes": supersedes,
            "from_user": user_id,
        }
        # replace same id if reclassified
        self.pins = [p for p in self.pins if p.get("id") != entry["id"]]
        self.pins.append(entry)
        if len(self.pins) > 200:
            seeds = [p for p in self.pins if str(p.get("id")).startswith("seed-")]
            rest = [p for p in self.pins if not str(p.get("id")).startswith("seed-")]
            self.pins = seeds + rest[-180:]
        return entry

    def snapshot(self) -> List[Dict[str, Any]]:
        return [dict(p) for p in self.pins]


def live_pin_decide(
    *,
    this_user: str,
    when: str,
    prior_users: List[str],
    pin_statuses: str,
    live: bool,
) -> Tuple[str, str, Optional[str], Optional[str], float, str]:
    """Return (status, pin_text, corr, supersedes, jev_ms, model)."""
    state = (
        f"TIMESTAMP: {when}\n"
        f"CURRENT USER MESSAGE:\n{this_user[:2500]}\n\n"
        f"ALL PRIOR USER MESSAGES ({len(prior_users)}):\n"
        + "\n---\n".join(u[:600] for u in prior_users[-80:])
        + f"\n\nCURRENT PIN STATUSES:\n{pin_statuses[-3500:]}\n"
    )
    instructions = (
        "Classify this USER message into ONE epistemic pin status for the living pin store. "
        "exploring = probing/uncertain, do not harden. "
        "soft = provisional preference. "
        "hard = durable MUST/NEVER lock. "
        "superseded = take-back / reconsider prior pin. "
        "Human intent beats agent data claims."
    )
    criteria = {
        "exploring": "user is probing, reconsidering, or ambiguous — do not harden",
        "soft": "provisional preference / soft constraint",
        "hard": "durable MUST/NEVER/ONLY lock the agent must obey",
        "superseded": "user takes back or reopens a prior pin",
    }
    if not (live and jev_decide.live_enabled() and jev_decide._key()):
        # deterministic fallback (should not happen in live runs)
        low = this_user.lower()
        if any(w in low for w in ("wait why", "actually", "reconsider", "undo", "never mind")):
            return "superseded", this_user[:200], None, None, 0.0, "deterministic"
        if re.search(r"\b(MUST|NEVER|ONLY)\b", this_user):
            return "hard", this_user[:200], None, None, 0.0, "deterministic"
        if "?" in this_user or len(this_user) < 40:
            return "exploring", this_user[:200], None, None, 0.0, "deterministic"
        return "soft", this_user[:200], None, None, 0.0, "deterministic"
    try:
        choice, conf, model, jev_ms = jev_decide.decide_choice(
            state[:6000],
            "pin_status",
            instructions,
            criteria,
            timeout_s=45.0,
        )
        status = choice if choice in EPISTEMIC else "exploring"
        return status, this_user[:200], f"conf={conf}", None, jev_ms, model
    except Exception as e:
        return "exploring", this_user[:200], f"err_{type(e).__name__}", None, 0.0, "error"


# ---------- Event harvest ----------

def harvest_claude_events(jsonl_dir: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    files = sorted(jsonl_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    for path in files:
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            when = str(row.get("timestamp") or row.get("created_at") or "")
            msg = row.get("message") or {}
            role = (msg.get("role") or row.get("type") or "").lower()
            content = msg.get("content")
            # user text
            if role in ("user", "human") or row.get("type") == "user":
                text = ""
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts = []
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "text":
                            parts.append(str(b.get("text") or ""))
                        elif isinstance(b, str):
                            parts.append(b)
                    text = "\n".join(parts)
                text = redact(text).strip()
                if text and not text.startswith("<") and len(text) > 1:
                    uid = hashlib.sha1(f"{path.name}|{i}|{text[:120]}".encode()).hexdigest()[:12]
                    events.append(
                        {
                            "id": f"claude-user-{uid}",
                            "kind": "user",
                            "stream": "claude_tx",
                            "when": when,
                            "text": text[:4000],
                            "source": path.name,
                        }
                    )
            # tools
            if isinstance(content, list):
                for block in content:
                    if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                        continue
                    name = block.get("name") or "unknown"
                    inp = block.get("input") or {}
                    if isinstance(inp, dict) and "command" in inp:
                        args = redact(str(inp.get("command") or ""))[:1200]
                    else:
                        args = redact(json.dumps(inp, ensure_ascii=False)[:1200])
                    tid = str(block.get("id") or hashlib.sha1(f"{name}|{args[:80]}".encode()).hexdigest()[:10])
                    events.append(
                        {
                            "id": f"claude-tool-{tid}",
                            "kind": "tool",
                            "stream": "claude_tx",
                            "when": when,
                            "proposed_tool": {"name": name, "args_summary": args},
                            "text": f"{name} {args}"[:400],
                            "source": path.name,
                        }
                    )
    events.sort(key=lambda e: (str(e.get("when") or ""), str(e.get("id") or "")))
    return events


def harvest_acs_events(gold_path: Path, tools_path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if gold_path.is_file():
        data = json.loads(gold_path.read_text(encoding="utf-8-sig"))
        for turn in data.get("turns") or []:
            events.append(
                {
                    "id": turn.get("id") or f"acs-user-{len(events)}",
                    "kind": "user",
                    "stream": "acs_tx",
                    "when": turn.get("when") or "",
                    "text": str(turn.get("text") or "")[:4000],
                    "source": "acs_chat_gold/turns.json",
                    "pins_add": list(turn.get("pins_add") or []),
                    "pins_supersede": list(turn.get("pins_supersede") or []),
                    "gold_meta": turn.get("gold"),
                }
            )
    if tools_path.is_file():
        for line in tools_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            tool = row.get("proposed_tool") or {}
            events.append(
                {
                    "id": row.get("id") or f"acs-tool-{len(events)}",
                    "kind": "tool",
                    "stream": "acs_tx",
                    "when": row.get("when") or "",
                    "proposed_tool": {
                        "name": tool.get("name") or "Shell",
                        "args_summary": redact(str(tool.get("args_summary") or ""))[:1200],
                    },
                    "text": redact(str(tool.get("args_summary") or ""))[:400],
                    "source": row.get("source") or "acs_tx/tools.jsonl",
                }
            )
    events.sort(key=lambda e: (str(e.get("when") or ""), str(e.get("id") or "")))
    return events


# ---------- Lane runners with optional shared pin front ----------

def run_lanes_for_tool(
    pack: Dict[str, Any],
    *,
    live: bool,
    ablation: str,
    epi_pins: List[str],
    baseline_pins: List[str],
) -> Dict[str, Any]:
    """ablation A: only L1 gets epi_pins; B: all lanes get epi_pins."""
    tool = pack.get("proposed_tool") or {}
    cmd = str(tool.get("args_summary") or "")

    # Hard denylist first — 0 Jev
    hd = pol.hard_deny_reasons(cmd) if cmd else []
    if hd:
        deny_res = {
            "decision": "deny",
            "reason_code": "hard_deny:" + ",".join(hd),
            "layer": "hard_deny",
            "jev_ms": 0,
            "agree": None,
            "fn": 0,
            "fp": 0,
        }
        return {
            "id": pack.get("id"),
            "kind": "tool",
            "stream": pack.get("stream"),
            "when": pack.get("when"),
            "text": pack.get("text"),
            "hard_deny": True,
            "lanes": {lid: dict(deny_res) for lid in LANE_IDS},
            "pin_trace": pack.get("pin_trace"),
        }

    def pins_for(lid: str) -> List[str]:
        if ablation == "B":
            return epi_pins[-24:]
        # A: L1 only gets epistemic; others baseline
        if lid == "L1_acs":
            return epi_pins[-24:]
        return baseline_pins[-16:]

    lane_out: Dict[str, Any] = {}
    raw: Dict[str, Any] = {}
    for lid, fn in mlw.LANES:
        p = dict(pack)
        use_pins = pins_for(lid)
        p["brief"] = "ACS epistemic pins:\n- " + "\n- ".join(use_pins)
        p["corrections"] = list(use_pins)
        try:
            res = fn(p, live=live)
        except Exception as e:
            res = {
                "lane_id": lid,
                "decision": "escalate",
                "reason_code": f"lane_err_{type(e).__name__}",
                "layer": "error",
                "latency_ms": 0,
                "jev_ms": 0,
            }
        raw[lid] = res
        lane_out[lid] = {
            "decision": res.get("decision"),
            "layer": res.get("layer"),
            "jev_ms": res.get("jev_ms"),
            "reason": res.get("reason_code"),
            "agree": None,
            "fn": 0,
            "fp": 0,
            "pins_n": len(use_pins),
            "pin_front": ablation == "B" or lid == "L1_acs",
        }
    return {
        "id": pack.get("id"),
        "kind": "tool",
        "stream": pack.get("stream"),
        "when": pack.get("when"),
        "text": pack.get("text"),
        "hard_deny": False,
        "lanes": lane_out,
        "raw": {k: {kk: vv for kk, vv in v.items() if kk != "pins"} for k, v in raw.items()},
        "pin_trace": pack.get("pin_trace"),
    }


# ---------- Walk one stream ----------

def walk_stream(
    events: List[Dict[str, Any]],
    *,
    stream: str,
    ablation: str,
    live: bool,
    workers: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    store = EpistemicPinStore()
    baseline = store.baseline_only()
    prior_users: List[str] = []
    rows: List[Dict[str, Any]] = []
    pin_traces: List[Dict[str, Any]] = []
    user_n = tool_n = hard_deny_n = 0
    pin_jev_ms: List[float] = []

    # Phase 1: sequential USER pin-decide (order matters for living store)
    # Collect tool packs with pin snapshot at that point in time
    tool_packs: List[Dict[str, Any]] = []
    for ev in events:
        if ev.get("kind") == "user":
            user_n += 1
            text = str(ev.get("text") or "")
            when = str(ev.get("when") or "")
            # gold-seeded supersede/add if present (ACS)
            for s in ev.get("pins_supersede") or []:
                store.apply_decision(
                    user_id=str(ev.get("id")) + "-sup",
                    user_text=s,
                    when=when,
                    status="superseded",
                    pin_text=s,
                )
            status, pin_text, corr, supersedes, jms, model = live_pin_decide(
                this_user=text,
                when=when,
                prior_users=list(prior_users),
                pin_statuses=store.statuses_brief(),
                live=live,
            )
            pin_jev_ms.append(jms)
            entry = store.apply_decision(
                user_id=str(ev.get("id")),
                user_text=text,
                when=when,
                status=status,
                pin_text=pin_text,
                corr=corr,
                supersedes=supersedes,
            )
            for p in ev.get("pins_add") or []:
                store.apply_decision(
                    user_id=str(ev.get("id")) + "-add",
                    user_text=p,
                    when=when,
                    status="hard" if re.search(r"\b(MUST|NEVER|ONLY)\b", p) else "soft",
                    pin_text=p,
                )
            prior_users.append(f"[{when}] {text}")
            trace = {
                "id": ev.get("id"),
                "kind": "user_pin",
                "stream": stream,
                "when": when,
                "status": status,
                "pin_text": pin_text[:240],
                "jev_ms": round(jms, 2),
                "model": model,
                "ablation": ablation,
                "active_soft_hard_n": len(store.active_soft_hard()),
                "store_n": len(store.pins),
            }
            pin_traces.append(trace)
            rows.append({**trace, "lanes": {}, "text": text[:400]})
        else:
            tool_n += 1
            snap = store.snapshot()
            epi = [p["text"] for p in snap if p.get("status") in ("soft", "hard")]
            pack = {
                "id": ev.get("id"),
                "stream": stream,
                "when": ev.get("when"),
                "axis": "tools",
                "proposed_tool": ev.get("proposed_tool") or {"name": "Unknown", "args_summary": ""},
                "text": ev.get("text"),
                "gold_decision": None,
                "pin_trace": {
                    "ablation": ablation,
                    "epi_n": len(epi),
                    "baseline_n": len(baseline),
                    "statuses_tail": [
                        {"status": p.get("status"), "text": (p.get("text") or "")[:80]}
                        for p in snap[-8:]
                    ],
                },
                "_epi_pins": epi,
                "_baseline_pins": list(baseline),
            }
            tool_packs.append(pack)

    # Phase 2: tool gates in parallel (pin snapshot frozen per pack at harvest time)
    print(
        f"stream={stream} ablation={ablation} users={user_n} tools={tool_n} "
        f"pin_traces={len(pin_traces)} launching tools workers={workers}",
        flush=True,
    )
    t0 = time.perf_counter()

    def _one(p: Dict[str, Any]) -> Dict[str, Any]:
        return run_lanes_for_tool(
            p,
            live=live,
            ablation=ablation,
            epi_pins=list(p.get("_epi_pins") or []),
            baseline_pins=list(p.get("_baseline_pins") or baseline),
        )

    tool_rows: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(_one, p): p for p in tool_packs}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            tool_rows.append(r)
            done += 1
            if done % 50 == 0 or done == len(tool_packs):
                print(f"progress {stream}/{ablation} tools {done}/{len(tool_packs)}", flush=True)
    wall = (time.perf_counter() - t0) * 1000
    hard_deny_n = sum(1 for r in tool_rows if r.get("hard_deny"))
    rows.extend(tool_rows)
    rows.sort(key=lambda r: (str(r.get("when") or ""), str(r.get("id") or "")))

    # pairwise on tool rows only
    pairwise = {"pairs": {}, "n": len(tool_rows)}
    for a, b in combinations(LANE_IDS, 2):
        same = scored = 0
        for r in tool_rows:
            da = ((r.get("lanes") or {}).get(a) or {}).get("decision")
            db = ((r.get("lanes") or {}).get(b) or {}).get("decision")
            if not da or not db:
                continue
            scored += 1
            if da == db:
                same += 1
        pairwise["pairs"][f"{a}__{b}"] = {
            "same": same,
            "scored": scored,
            "agree_pct": round(100.0 * same / scored, 1) if scored else None,
        }

    verdicts: Dict[str, Dict[str, int]] = {}
    for lid in LANE_IDS:
        c = {"allow": 0, "deny": 0, "escalate": 0, "other": 0}
        for r in tool_rows:
            d = ((r.get("lanes") or {}).get(lid) or {}).get("decision") or "other"
            if d in c:
                c[d] += 1
            else:
                c["other"] += 1
        verdicts[lid] = c

    status_hist = {"exploring": 0, "soft": 0, "hard": 0, "superseded": 0}
    for t in pin_traces:
        s = t.get("status") or "exploring"
        if s in status_hist:
            status_hist[s] += 1

    summary = {
        "run_id": datetime.now(timezone.utc).strftime(
            f"ftx-{ablation.lower()}-{stream}-%Y%m%dT%H%M%SZ"
        ),
        "kind": "full_tx_ab_walkforward",
        "ablation": ablation,
        "stream": stream,
        "live": live,
        "sha": git_sha(),
        "n_user": user_n,
        "n_tool": tool_n,
        "n_hard_deny": hard_deny_n,
        "n_events": len(events),
        "pairwise": pairwise,
        "verdicts": verdicts,
        "pin_status_hist": status_hist,
        "pin_traces_sample": pin_traces[:40],
        "pin_jev_p50_ms": round(statistics.median(pin_jev_ms), 1) if pin_jev_ms else None,
        "tool_wall_ms": round(wall, 1),
        "workers": workers,
        "model": os.environ.get("ACS_JEV_MODEL") or "typesafe/jev-1.13",
        "notes": (
            f"Full-TX ablation {ablation}: "
            + (
                "epistemic pin feeds L1 only"
                if ablation == "A"
                else "epistemic pin shared in FRONT of L1-L5"
            )
            + f"; stream={stream} separate; uncapped live Jev"
        ),
    }
    return rows, summary


def append_html(summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> Path:
    report = ROOT / "reports" / "jev-oss-compare.html"
    rid = summary["run_id"]
    # peer flat for existing append
    flat = []
    tool_rows = [r for r in rows if r.get("kind") == "tool" or (r.get("lanes") and not r.get("kind") == "user_pin")]
    for r in tool_rows:
        if r.get("kind") == "user_pin":
            continue
        l1 = (r.get("lanes") or {}).get("L1_acs") or {}
        l2 = (r.get("lanes") or {}).get("L2_auto") or {}
        flat.append(
            {
                "id": r.get("id"),
                "gold": None,
                "acs_decision": l1.get("decision"),
                "acs_layer": l1.get("layer"),
                "auto_decision": l2.get("decision"),
                "auto_layer": l2.get("layer"),
                "jev_ms": max(float(l1.get("jev_ms") or 0), float(l2.get("jev_ms") or 0)),
                "agree": l1.get("decision") == l2.get("decision"),
                "fn": 0,
                "fp": 0,
            }
        )
    html_report.append_run(
        report,
        {
            **summary,
            "agree": sum(1 for r in flat if r.get("agree")),
            "disagree": sum(1 for r in flat if not r.get("agree")),
            "n_packs": summary.get("n_tool"),
            "notes": summary.get("notes"),
        },
        flat,
    )
    # rich block
    lines = [
        f'<section class="run" data-run-id="{rid}" id="run-{rid}">',
        f"<h3>Full-TX Ablation {html_report._esc(summary.get('ablation'))} — "
        f"{html_report._esc(summary.get('stream'))} — {rid}</h3>",
        f"<p>n_user=<strong>{summary.get('n_user')}</strong> "
        f"n_tool=<strong>{summary.get('n_tool')}</strong> "
        f"hard_deny=<strong>{summary.get('n_hard_deny')}</strong> "
        f"pin_hist={html_report._esc(json.dumps(summary.get('pin_status_hist')))} "
        f"live={summary.get('live')} model={html_report._esc(summary.get('model'))}</p>",
        "<h4>Pairwise lane agree %</h4><ul>",
    ]
    for k, v in ((summary.get("pairwise") or {}).get("pairs") or {}).items():
        lines.append(
            f"<li><code>{html_report._esc(k)}</code>: {v.get('agree_pct')}% "
            f"({v.get('same')}/{v.get('scored')})</li>"
        )
    lines.append("</ul><h4>Verdicts</h4><table class='table table-dark table-sm'><thead><tr>"
                 "<th>Lane</th><th>allow</th><th>deny</th><th>escalate</th></tr></thead><tbody>")
    for lid, vc in (summary.get("verdicts") or {}).items():
        lines.append(
            f"<tr><td>{lid}</td><td>{vc.get('allow')}</td><td>{vc.get('deny')}</td>"
            f"<td>{vc.get('escalate')}</td></tr>"
        )
    lines.append("</tbody></table><h4>Pin traces sample</h4><ul>")
    for t in (summary.get("pin_traces_sample") or [])[:25]:
        lines.append(
            f"<li><code>{html_report._esc(t.get('id'))}</code> "
            f"[{html_report._esc(t.get('status'))}] "
            f"{html_report._esc(t.get('pin_text'))}</li>"
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


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ablation", choices=["A", "B"], required=True)
    ap.add_argument("--stream", choices=["acs", "claude"], required=True)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--append-html", action="store_true")
    ap.add_argument("--claude-jsonl-dir", type=str, default="")
    ap.add_argument("--chunk", type=int, default=0)
    args = ap.parse_args(argv)

    repo = ROOT.parents[3] if (ROOT.parents[3] / ".git").exists() else Path.cwd()
    _load_dotenv(
        [
            repo / ".env",
            Path.home() / "configs.env",
            Path.home() / "agent-custom-setup" / ".env",
        ]
    )
    if args.live:
        os.environ["ACS_JEV_LIVE"] = "1"
    live = bool(args.live and jev_decide.live_enabled() and jev_decide._key())
    print(f"live={live} ablation={args.ablation} stream={args.stream}", flush=True)

    if args.stream == "acs":
        events = harvest_acs_events(
            ROOT / "fixtures" / "acs_chat_gold" / "turns.json",
            ROOT / "fixtures" / "acs_tx" / "tools.jsonl",
        )
        stream_name = "acs_tx"
    else:
        cdir = Path(args.claude_jsonl_dir) if args.claude_jsonl_dir else Path.home() / "claude-hades-v2-jsonl"
        if not cdir.is_dir():
            # fallback to pre-harvested tools only
            print(f"WARN missing {cdir}; falling back to fixtures/claude_tx/tools.jsonl", flush=True)
            events = []
            tools = ROOT / "fixtures" / "claude_tx" / "tools.jsonl"
            for line in tools.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                tool = row.get("proposed_tool") or {}
                events.append(
                    {
                        "id": row.get("id"),
                        "kind": "tool",
                        "stream": "claude_tx",
                        "when": row.get("when"),
                        "proposed_tool": tool,
                        "text": str(tool.get("args_summary") or "")[:400],
                        "source": "fixtures/claude_tx",
                    }
                )
        else:
            events = harvest_claude_events(cdir)
        stream_name = "claude_tx"

    if args.chunk and args.chunk > 0:
        events = events[: args.chunk]

    n_user = sum(1 for e in events if e.get("kind") == "user")
    n_tool = sum(1 for e in events if e.get("kind") == "tool")
    print(f"events n={len(events)} user={n_user} tool={n_tool}", flush=True)

    rows, summary = walk_stream(
        events,
        stream=stream_name,
        ablation=args.ablation,
        live=live,
        workers=args.workers,
    )
    runs = ROOT / "reports" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    out = runs / f"{summary['run_id']}.json"
    # Write summary + compact rows (drop huge raw)
    compact_rows = []
    for r in rows:
        cr = {k: v for k, v in r.items() if k != "raw"}
        compact_rows.append(cr)
    out.write_text(json.dumps({"summary": summary, "rows": compact_rows}, indent=2) + "\n", encoding="utf-8")
    latest = runs / f"ftx-{args.ablation.lower()}-{args.stream}-latest.json"
    latest.write_text(json.dumps({"summary": summary}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "pin_traces_sample"}, indent=2), flush=True)
    if args.append_html:
        p = append_html(summary, rows)
        print(f"appended_html={p}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
