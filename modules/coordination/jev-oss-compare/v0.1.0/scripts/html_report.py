#!/usr/bin/env python3
"""Multi-page appendable HTML comparison report (Tabler dark + CGM HSW voice).

Uses Tabler Core (CDN) forced dark-only. Pages via sidebar nav: overview,
method, pipeline, results, charts, disagreements, routing checks, append.
Newest run sections stay prepended under history. Blind routing sections
are preserved across appends.
"""
from __future__ import annotations
import html, json, re
from pathlib import Path
from typing import Any, Dict, List, Optional

REPORT_NAME = "ACS Jev gate comparison"
TABLER_CSS = "https://cdn.jsdelivr.net/npm/@tabler/core@1.5.1/dist/css/tabler.min.css"
TABLER_JS = "https://cdn.jsdelivr.net/npm/@tabler/core@1.5.1/dist/js/tabler.min.js"
MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"
CHART_JS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"

SHELL = """<!DOCTYPE html>
<html lang="en" data-bs-theme="dark" style="color-scheme:dark;background:#0b0f14">
<head>
<meta charset="utf-8"/>
<meta name="color-scheme" content="dark only"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="theme-color" content="#0b0f14"/>
<title>{title}</title>
<link rel="stylesheet" href="{tabler_css}"/>
<style>
  html, body {{ color-scheme: dark; background: #0b0f14 !important; }}
  .page-section {{ display: none; }}
  .page-section.active {{ display: block; }}
  .mono {{ font-family: var(--tblr-font-monospace), ui-monospace, Menlo, Consolas, monospace; font-size: .85rem; }}
  .chart-wrap {{ min-height: 220px; }}
  .mermaid {{ overflow-x: auto; }}
  pre.append {{ background: var(--tblr-bg-surface-secondary); border: 1px solid var(--tblr-border-color); padding: .85rem; overflow-x: auto; border-radius: var(--tblr-border-radius); color: var(--tblr-body-color); }}
  .nav-link.active-page {{ background: rgba(var(--tblr-primary-rgb), .15); color: var(--tblr-primary) !important; }}
  section.run {{ margin-top: 1.25rem; padding-top: 1rem; border-top: 1px solid var(--tblr-border-color); }}
  .ok {{ color: var(--tblr-success); }}
  .bad {{ color: var(--tblr-danger); }}
  .navbar-vertical .navbar-brand {{ font-weight: 700; letter-spacing: .01em; }}
</style>
<script>
  (function () {{
    document.documentElement.setAttribute("data-bs-theme", "dark");
    try {{ localStorage.setItem("tabler-theme", "dark"); }} catch (e) {{}}
  }})();
</script>
<script src="{mermaid_js}"></script>
<script src="{chart_js}"></script>
</head>
<body>
<div class="page">
  <aside class="navbar navbar-vertical navbar-expand-lg" data-bs-theme="dark">
    <div class="container-fluid">
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#sidebar-menu" aria-controls="sidebar-menu" aria-expanded="false" aria-label="Toggle navigation">
        <span class="navbar-toggler-icon"></span>
      </button>
      <h1 class="navbar-brand navbar-brand-autodark">
        <span class="navbar-brand-text">ACS · Jev compare</span>
      </h1>
      <div class="collapse navbar-collapse" id="sidebar-menu">
        <ul class="navbar-nav pt-lg-3" id="report-nav" aria-label="Report pages">
          <li class="nav-item"><a class="nav-link active-page" href="#overview" data-page="overview"><span class="nav-link-title">Overview</span></a></li>
          <li class="nav-item"><a class="nav-link" href="#method" data-page="method"><span class="nav-link-title">Method</span></a></li>
          <li class="nav-item"><a class="nav-link" href="#pipeline" data-page="pipeline"><span class="nav-link-title">Pipeline</span></a></li>
          <li class="nav-item"><a class="nav-link" href="#results" data-page="results"><span class="nav-link-title">Results</span></a></li>
          <li class="nav-item"><a class="nav-link" href="#charts" data-page="charts"><span class="nav-link-title">Charts</span></a></li>
          <li class="nav-item"><a class="nav-link" href="#disagree" data-page="disagree"><span class="nav-link-title">Disagreements</span></a></li>
          <li class="nav-item"><a class="nav-link" href="#routing" data-page="routing"><span class="nav-link-title">Routing checks</span></a></li>
          <li class="nav-item"><a class="nav-link" href="#append" data-page="append"><span class="nav-link-title">Append next run</span></a></li>
        </ul>
        <div class="mt-auto mb-3 px-3 text-secondary small">
          Tabler dark · CGM HSW · no secrets
        </div>
      </div>
    </div>
  </aside>

  <div class="page-wrapper">
    <div class="page-header d-print-none">
      <div class="container-xl">
        <div class="row g-2 align-items-center">
          <div class="col">
            <div class="page-pretitle">Jev OSS compare · ACS-25</div>
            <h2 class="page-title">{title}</h2>
            <div class="text-secondary mt-1">{lede}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="page-body">
      <div class="container-xl">

        <section class="page-section active" id="page-overview" data-page="overview">
          <h3 class="mb-3">Overview</h3>
          {overview}
        </section>

        <section class="page-section" id="page-method" data-page="method">
          <div class="card mb-3">
            <div class="card-header"><h3 class="card-title">How we compared</h3></div>
            <div class="card-body">{method}</div>
          </div>
          <div class="card">
            <div class="card-header"><h3 class="card-title">What we kept and what we skipped</h3></div>
            <div class="card-body">{decision}</div>
          </div>
        </section>

        <section class="page-section" id="page-pipeline" data-page="pipeline">
          <div class="card mb-3">
            <div class="card-header"><h3 class="card-title">Pipeline</h3></div>
            <div class="card-body">
              <p class="text-secondary">Two short diagrams. ACS prefers fewer, simpler Mermaid charts.</p>
              <div class="mermaid">
flowchart LR
  A[Tool pack] --> B[Pin extract]
  B --> C[Gather package]
  C --> D{{Mock or live Jev}}
  D --> E[Allow / deny / escalate]
              </div>
              <div class="mermaid">
flowchart TB
  P[Same pack] --> ACS[ACS lane]
  P --> AUTO[Auto-mode lane]
  ACS --> CMP{{Agree?}}
  AUTO --> CMP
  AUTO --> HD[Hard-deny first]
  HD --> SAFE[Safe rules]
  SAFE --> JEV[Jev leftovers only]
              </div>
            </div>
          </div>
        </section>

        <section class="page-section" id="page-results" data-page="results">
          <div class="card">
            <div class="card-header"><h3 class="card-title">Results in plain English</h3></div>
            <div class="card-body">{results}</div>
          </div>
        </section>

        <section class="page-section" id="page-charts" data-page="charts">
          <h3 class="mb-3">Charts</h3>
          {charts}
        </section>

        <section class="page-section" id="page-disagree" data-page="disagree">
          <div class="card">
            <div class="card-header"><h3 class="card-title">Where the lanes disagreed</h3></div>
            <div class="card-body">{disagree}</div>
          </div>
        </section>

        <section class="page-section" id="page-routing" data-page="routing">
          <h3 class="mb-3">Live Jev routing checks</h3>
          {routing}
          <!--BLIND-->
        </section>

        <section class="page-section" id="page-append" data-page="append">
          <div class="card mb-3">
            <div class="card-header"><h3 class="card-title">How to append the next run</h3></div>
            <div class="card-body">{append_howto}</div>
          </div>
          <div class="card">
            <div class="card-header"><h3 class="card-title">Run history</h3></div>
            <div class="card-body">
              <p class="text-secondary">Newest sections appear at the top. Each run keeps its own table so later benches do not overwrite earlier numbers.</p>
              <div id="runs">
              <!--RUNS-->
              </div>
            </div>
          </div>
        </section>

      </div>
    </div>

    <footer class="footer footer-transparent d-print-none">
      <div class="container-xl">
        <div class="text-secondary">
          Built on <span class="mono">Tabler</span> dark (CDN) with ACS CGM html-demo structure and human-sounding-writing voice.
          Live path uses OpenRouter <span class="mono">typesafe/jev-1.13</span> (fast Jev OK). Secrets never printed. Ultrafast skipped. No Redis.
        </div>
      </div>
    </footer>
  </div>
</div>

<script src="{tabler_js}"></script>
<script>
(function () {{
  document.documentElement.setAttribute("data-bs-theme", "dark");
  const links = Array.from(document.querySelectorAll("#report-nav [data-page]"));
  const pages = Array.from(document.querySelectorAll(".page-section"));
  function show(id) {{
    pages.forEach(p => p.classList.toggle("active", p.dataset.page === id));
    links.forEach(a => a.classList.toggle("active-page", a.dataset.page === id));
    if (location.hash !== "#" + id) history.replaceState(null, "", "#" + id);
  }}
  links.forEach(a => a.addEventListener("click", (e) => {{
    e.preventDefault();
    show(a.dataset.page);
  }}));
  const initial = (location.hash || "#overview").slice(1);
  show(links.some(a => a.dataset.page === initial) ? initial : "overview");
  if (window.mermaid) {{
    mermaid.initialize({{ startOnLoad: true, theme: "dark", securityLevel: "loose" }});
  }}
  {chart_boot}
}})();
</script>
</body>
</html>
"""


def _esc(s: Any) -> str:
    return html.escape(str(s) if s is not None else "")


def _pct(n: int, d: int) -> str:
    if not d:
        return "0%"
    return f"{(100.0 * n / d):.1f}%"


def _ms(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.1f} ms"
    except (TypeError, ValueError):
        return "—"


def _overview_block(summary: Optional[Dict[str, Any]]) -> str:
    if not summary:
        return (
            "<div class='alert alert-info' role='alert'>"
            "No compare run has been appended yet. Harvest packs, run "
            "<span class='mono'>compare_run.py --cap 60 --live --append-html</span>, "
            "then reopen this file.</div>"
        )
    n = int(summary.get("n_packs") or 0)
    agree = int(summary.get("agree") or 0)
    disagree = int(summary.get("disagree") or 0)
    agree_pct = summary.get("agree_pct")
    if agree_pct is None and n:
        agree_pct = round(100.0 * agree / n, 1)
    live = "live Jev" if summary.get("live") else "mock only"
    return f"""
<p>On the Fish hosted-vs-selfhost fixture, ACS mock denied the self-host clone before any model call.
This page tracks whether an auto-mode-shaped hard-deny peer agrees, and what real Jev says when we ask it.</p>
<p>Latest run <span class="mono">{_esc(summary.get('run_id'))}</span> ({_esc(summary.get('started_at'))}, {live})
looked at <strong>{n} packs</strong>. The lanes matched on <strong>{agree} of {n}</strong>
({_esc(agree_pct)}% agreement) and differed on {disagree}.</p>
<div class="row row-cards mb-3">
  <div class="col-sm-6 col-lg-4"><div class="card card-sm"><div class="card-body">
    <div class="text-secondary">Packs compared</div>
    <div class="h1 mb-0">{n}</div>
    <div class="text-secondary small">Fish + fixtures + harvested Claude tool uses</div>
  </div></div></div>
  <div class="col-sm-6 col-lg-4"><div class="card card-sm"><div class="card-body">
    <div class="text-secondary">Agreement rate</div>
    <div class="h1 mb-0 text-success">{_esc(agree_pct)}%</div>
    <div class="text-secondary small">{agree} agree · {disagree} differ</div>
  </div></div></div>
  <div class="col-sm-6 col-lg-4"><div class="card card-sm"><div class="card-body">
    <div class="text-secondary">Missed denies (FN)</div>
    <div class="h1 mb-0">{_esc(summary.get('fn_vs_gold'))}</div>
    <div class="text-secondary small">Gold said deny, ACS did not</div>
  </div></div></div>
  <div class="col-sm-6 col-lg-4"><div class="card card-sm"><div class="card-body">
    <div class="text-secondary">False denies (FP)</div>
    <div class="h1 mb-0">{_esc(summary.get('fp_vs_gold'))}</div>
    <div class="text-secondary small">Gold said allow, ACS denied</div>
  </div></div></div>
  <div class="col-sm-6 col-lg-4"><div class="card card-sm"><div class="card-body">
    <div class="text-secondary">Jev latency p50</div>
    <div class="h1 mb-0">{_esc(_ms(summary.get('p50_jev_ms') or summary.get('median_jev_ms')))}</div>
    <div class="text-secondary small">Half of live Jev calls were this fast or faster</div>
  </div></div></div>
  <div class="col-sm-6 col-lg-4"><div class="card card-sm"><div class="card-body">
    <div class="text-secondary">Jev latency p95</div>
    <div class="h1 mb-0">{_esc(_ms(summary.get('p95_jev_ms')))}</div>
    <div class="text-secondary small">95th percentile live Jev call</div>
  </div></div></div>
</div>
"""


def _results_block(summary: Optional[Dict[str, Any]], rows: List[Dict[str, Any]]) -> str:
    if not summary:
        return "<p>No results yet.</p>"
    n = int(summary.get("n_packs") or len(rows))
    agree = int(summary.get("agree") or 0)
    disagree = int(summary.get("disagree") or 0)
    parts = [
        "<p>Numbers below are from the newest appended run. Labels stay in plain English on purpose.</p>",
        "<div class='table-responsive'><table class='table table-vcenter table-striped'>",
        "<thead><tr><th>What we measured</th><th>Value</th><th>Meaning</th></tr></thead><tbody>",
        f"<tr><td>Pack count</td><td class='mono'>{n}</td><td>How many tool packs both lanes saw</td></tr>",
        f"<tr><td>Agree</td><td class='mono text-success'>{agree} ({_pct(agree, n)})</td><td>ACS and auto-mode returned the same decision</td></tr>",
        f"<tr><td>Disagree</td><td class='mono'>{disagree} ({_pct(disagree, n)})</td><td>Lanes returned different decisions</td></tr>",
        f"<tr><td>False negatives vs gold</td><td class='mono'>{_esc(summary.get('fn_vs_gold'))}</td><td>Gold deny/block, ACS did not deny</td></tr>",
        f"<tr><td>False positives vs gold</td><td class='mono'>{_esc(summary.get('fp_vs_gold'))}</td><td>Gold allow, ACS denied</td></tr>",
        f"<tr><td>Jev latency p50</td><td class='mono'>{_esc(_ms(summary.get('p50_jev_ms') or summary.get('median_jev_ms')))}</td><td>Median live Jev round-trip</td></tr>",
        f"<tr><td>Jev latency p95</td><td class='mono'>{_esc(_ms(summary.get('p95_jev_ms')))}</td><td>Slow-tail live Jev round-trip</td></tr>",
        f"<tr><td>ACS lane p50 / p95</td><td class='mono'>{_esc(_ms(summary.get('p50_acs_ms')))} / {_esc(_ms(summary.get('p95_acs_ms')))}</td><td>End-to-end ACS pack latency</td></tr>",
        f"<tr><td>Wall clock</td><td class='mono'>{_esc(_ms(summary.get('wall_ms')))}</td><td>Whole compare with {_esc(summary.get('workers'))} workers</td></tr>",
        f"<tr><td>Mode</td><td class='mono'>{'live Jev' if summary.get('live') else 'mock only'}</td><td>Model {_esc(summary.get('model') or 'typesafe/jev-1.13')}</td></tr>",
        "</tbody></table></div>",
    ]
    if summary.get("notes"):
        parts.append(f"<p class='text-secondary mt-2'>{_esc(summary['notes'])}</p>")
    return "\n".join(parts)


def _disagree_block(rows: List[Dict[str, Any]]) -> str:
    bad = [r for r in rows if not r.get("agree")]
    if not bad:
        return "<p>No disagreements in the newest run. Both lanes matched on every pack.</p>"
    parts = [
        f"<p>{len(bad)} pack(s) where ACS and auto-mode differed. Useful for triage, not a scoreboard.</p>",
        "<div class='table-responsive'><table class='table table-vcenter table-striped'>",
        "<thead><tr><th>Pack</th><th>Gold</th><th>ACS</th><th>Auto-mode</th><th>Jev ms</th></tr></thead><tbody>",
    ]
    for r in bad:
        parts.append(
            "<tr>"
            f"<td class='mono'>{_esc(r.get('id'))}</td>"
            f"<td>{_esc(r.get('gold') or '—')}</td>"
            f"<td>{_esc(r.get('acs_decision'))} <span class='mono text-secondary'>({_esc(r.get('acs_layer'))})</span></td>"
            f"<td>{_esc(r.get('auto_decision'))} <span class='mono text-secondary'>({_esc(r.get('auto_layer'))})</span></td>"
            f"<td>{_esc(r.get('jev_ms'))}</td>"
            "</tr>"
        )
    parts.append("</tbody></table></div>")
    return "\n".join(parts)


def _charts_markup(summary: Optional[Dict[str, Any]], rows: List[Dict[str, Any]]) -> str:
    if not summary:
        return "<p class='text-secondary'>Charts appear after the first appended run.</p>"
    agree = int(summary.get("agree") or 0)
    disagree = int(summary.get("disagree") or 0)
    lat_ids = [str(r.get("id") or "")[:18] for r in rows[:40]]
    lat_jev = [float(r.get("jev_ms") or 0) for r in rows[:40]]
    lat_acs = [float(r.get("acs_ms") or 0) for r in rows[:40]]
    payload = json.dumps({
        "agree": agree,
        "disagree": disagree,
        "labels": lat_ids,
        "jev": lat_jev,
        "acs": lat_acs,
    }).replace("<", "\\u003c")
    nshow = min(40, len(rows))
    return f"""
<div class="row row-cards">
  <div class="col-lg-5">
    <div class="card">
      <div class="card-header"><h3 class="card-title">ACS and auto-mode matched on most packs</h3></div>
      <div class="card-body chart-wrap">
        <canvas id="agreeChart" aria-label="Agree versus disagree counts"></canvas>
      </div>
    </div>
  </div>
  <div class="col-lg-7">
    <div class="card">
      <div class="card-header"><h3 class="card-title">Jev and ACS latency stayed in the low hundreds of milliseconds</h3></div>
      <div class="card-body chart-wrap">
        <canvas id="latChart" aria-label="Latency per pack"></canvas>
        <p class="text-secondary small mt-2">First {nshow} packs shown so the line stays readable. Full table lives under Append next run → run history.</p>
      </div>
    </div>
  </div>
</div>
<script type="application/json" id="chart-data">{payload}</script>
"""


def _chart_boot() -> str:
    return """
  const raw = document.getElementById("chart-data");
  if (!raw || !window.Chart) return;
  let data;
  try { data = JSON.parse(raw.textContent); } catch (e) { return; }
  const tick = { color: "#8b97a8" };
  const grid = { color: "rgba(139,151,168,0.15)" };
  const agreeEl = document.getElementById("agreeChart");
  const latEl = document.getElementById("latChart");
  if (agreeEl) {
    new Chart(agreeEl, {
      type: "bar",
      data: {
        labels: ["Agree", "Disagree"],
        datasets: [{ label: "Packs", data: [data.agree, data.disagree],
          backgroundColor: ["#2fb344", "#d63939"] }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false }, title: { display: false } },
        scales: {
          x: { ticks: tick, grid: grid },
          y: { beginAtZero: true, ticks: Object.assign({ precision: 0 }, tick), grid: grid }
        }
      }
    });
  }
  if (latEl) {
    new Chart(latEl, {
      type: "line",
      data: {
        labels: data.labels,
        datasets: [
          { label: "Jev ms", data: data.jev, borderColor: "#4299e1", backgroundColor: "rgba(66,153,225,0.15)", tension: 0.2, pointRadius: 2 },
          { label: "ACS ms", data: data.acs, borderColor: "#a855f7", backgroundColor: "rgba(168,85,247,0.12)", tension: 0.2, pointRadius: 2 }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom", labels: { color: "#c0c8d4" } } },
        scales: {
          x: { ticks: Object.assign({ maxRotation: 60, minRotation: 30, autoSkip: true, maxTicksLimit: 12 }, tick), grid: grid },
          y: { beginAtZero: true, title: { display: true, text: "milliseconds", color: "#8b97a8" }, ticks: tick, grid: grid }
        }
      }
    });
  }
"""


def _append_howto() -> str:
    return """
<p>Keep this HTML file. Each new bench prepends a run section and refreshes the Overview / Results / Charts / Disagreements pages from the newest summary.</p>
<pre class="append mono"># 1) Harvest more Claude transcripts (redacted) into fixtures
python modules/coordination/jev-oss-compare/v0.1.0/scripts/harvest_packs.py \\
  --claude-home --cap 60 --per-file 10 \\
  --out modules/coordination/jev-oss-compare/v0.1.0/fixtures/harvested/packs.json

# 2) Live compare (fast Jev OK) and append this report
set ACS_JEV_LIVE=1
python modules/coordination/jev-oss-compare/v0.1.0/scripts/compare_run.py \\
  --cap 60 --workers 8 --live --append-html
</pre>
<p>JSON for every run also lands under <span class="mono">reports/runs/</span>. Do not print <span class="mono">.env</span> secrets. Stay off <span class="mono">main</span> unless Alex asks.</p>
"""


def _routing_block(blind_summary: Optional[Dict[str, Any]] = None) -> str:
    if not blind_summary:
        return (
            "<div class='alert alert-secondary' role='status'>"
            "No live routing / blind-catch Jev append yet. Blind verdicts land here and under "
            "<span class='mono'>reports/runs/blind-*.json</span> when run.</div>"
        )
    bc = blind_summary.get("blind_catch") or {}
    rc = blind_summary.get("routing_correctness") or {}
    rid = _esc(blind_summary.get("run_id"))
    stamped = _esc(blind_summary.get("stamped"))
    endpoint = _esc(blind_summary.get("endpoint"))
    return f"""
<p class="text-secondary">Two parallel OpenRouter Decisions calls on a short pack of exact pre-complaint session words.
Questions stay separate on purpose: one asks whether smoke got mixed into live proof; the other asks whether
pytest-plus-HTML presentation was the right route for the ask. No later complaint text was shown to Jev.</p>
<p class="mono mb-3">run {rid} · {stamped} · endpoint {endpoint}</p>
<div class="row row-cards mb-3">
  <div class="col-md-6"><div class="card"><div class="card-body">
    <div class="text-secondary">Blind catch — smoke treated as live proof?</div>
    <div class="h2 mb-1">choice <span class="mono">{_esc(bc.get('choice'))}</span></div>
    <div>confidence <span class="mono">{_esc(bc.get('confidence'))}</span> · latency <span class="mono">{_esc(_ms(bc.get('latency_ms')))}</span></div>
    <div class="text-secondary small mt-1">model <span class="mono">{_esc(bc.get('model'))}</span></div>
  </div></div></div>
  <div class="col-md-6"><div class="card"><div class="card-body">
    <div class="text-secondary">Routing — pytest smoke + HTML/95% correct for the ask?</div>
    <div class="h2 mb-1">choice <span class="mono">{_esc(rc.get('choice'))}</span></div>
    <div>confidence <span class="mono">{_esc(rc.get('confidence'))}</span> · latency <span class="mono">{_esc(_ms(rc.get('latency_ms')))}</span></div>
    <div class="text-secondary small mt-1">model <span class="mono">{_esc(rc.get('model'))}</span></div>
  </div></div></div>
</div>
"""


def build_shell(
    summary: Optional[Dict[str, Any]] = None,
    rows: Optional[List[Dict[str, Any]]] = None,
    blind_summary: Optional[Dict[str, Any]] = None,
) -> str:
    rows = rows or []
    lede = (
        "On the Fish hosted-vs-selfhost fixture, ACS mock denied the self-host clone before any model call. "
        "This multi-page report tracks agreement, misses, and latency across ACS and an auto-mode-shaped peer."
    )
    method = """
<p>Two lanes see the same tool packs. ACS runs pin extract, builds a small gather package, then mock or live Jev.
The auto-mode peer applies hard-deny patterns first (never Jev), then safe/user rules, then Jev only for leftovers.
A third stub checks post-run criteria the way <span class="mono">jev-gate</span> would — not as PreToolUse.</p>
<p>Packs come from Fish fixtures, hard-deny corpus, research claims, and harvested Claude/session-ops tool_use rows (redacted).
Benches cap pack count and call Jev in parallel. No LLM-as-coder in the loop.</p>
"""
    decision = """
<div class="table-responsive"><table class="table table-vcenter table-striped">
<thead><tr><th>Candidate</th><th>Call</th><th>Why</th></tr></thead>
<tbody>
<tr><td>jomatsu/pi-jev-auto-mode</td><td>ADAPT_PATTERN</td><td>Port hard-deny matrix into compare peer; Pi package does not run on Claude/Kilo</td></tr>
<tr><td>TheoOliveira/pi-jev (jev-gate)</td><td>ADAPT_PATTERN</td><td>Optional post-run stub only</td></tr>
<tr><td>jkudish/jev-mcp</td><td>USE (optional dep)</td><td>MCP judgments; ACS keeps packer+hooks</td></tr>
<tr><td>ctmx/openrouter-jev-mcp</td><td>ADAPT / thin helper</td><td>ACS already has openrouter_jev.py</td></tr>
<tr><td>tamaratran/fast-jev-compaction</td><td>SKIP for now</td><td>Compaction, not tool gate</td></tr>
<tr><td>browser-use/jev-ultrafast</td><td>SKIP</td><td>Browser only</td></tr>
<tr><td>FuJuntao/pi-permission-gate</td><td>ADAPT_PATTERN (ref)</td><td>Overlaps auto-mode catalogue</td></tr>
<tr><td>can1357/oh-my-pi</td><td>SKIP</td><td>No drop-in coding-tool gate for ACS</td></tr>
</tbody>
</table></div>
<p class="mt-2">Claude and Kilo keep ACS adapters live. HOTLOAD default stays ACS pin → pack → Jev.</p>
"""
    return SHELL.format(
        title=_esc(REPORT_NAME),
        lede=lede,
        overview=_overview_block(summary),
        method=method,
        decision=decision,
        results=_results_block(summary, rows),
        charts=_charts_markup(summary, rows),
        disagree=_disagree_block(rows),
        routing=_routing_block(blind_summary),
        append_howto=_append_howto(),
        chart_boot=_chart_boot(),
        tabler_css=TABLER_CSS,
        tabler_js=TABLER_JS,
        mermaid_js=MERMAID_JS,
        chart_js=CHART_JS,
    )


def render_run_section(summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
    rid = _esc(summary.get("run_id"))
    when = _esc(summary.get("started_at"))
    n = summary.get("n_packs", len(rows))
    agree = summary.get("agree", 0)
    disagree = summary.get("disagree", 0)
    agree_pct = summary.get("agree_pct")
    if agree_pct is None and n:
        agree_pct = round(100.0 * int(agree) / int(n), 1)
    fn = summary.get("fn_vs_gold", 0)
    fp = summary.get("fp_vs_gold", 0)
    live = "live Jev" if summary.get("live") else "mock only"
    p50 = summary.get("p50_jev_ms", summary.get("median_jev_ms"))
    p95 = summary.get("p95_jev_ms")
    parts = [
        f'<section class="run" data-run-id="{rid}" id="run-{rid}">',
        f"<h4>Run {rid}</h4>",
        f"<p>{when}. {n} packs, {live}. Agreement ACS vs auto-mode: "
        f"<strong class='ok'>{agree} agree ({_esc(agree_pct)}%)</strong>, {disagree} differ. "
        f"Against gold where present: FN={fn}, FP={fp}."
        + (f" Jev p50 {_esc(_ms(p50))}, p95 {_esc(_ms(p95))}." if p50 is not None or p95 is not None else "")
        + "</p>",
        "<div class='table-responsive'><table class='table table-sm table-vcenter table-striped'>",
        "<thead><tr>"
        "<th>Pack</th><th>Gold</th><th>ACS</th><th>Auto-mode</th><th>Agree</th>"
        "<th>ACS ms</th><th>Auto ms</th><th>Jev ms</th></tr></thead><tbody>",
    ]
    for r in rows:
        ag = r.get("agree")
        ag_s = "<span class='ok'>yes</span>" if ag else "<span class='bad'>no</span>"
        parts.append(
            "<tr>"
            f"<td class='mono'>{_esc(r.get('id'))}</td>"
            f"<td>{_esc(r.get('gold') or '—')}</td>"
            f"<td>{_esc(r.get('acs_decision'))} <span class='mono text-secondary'>({_esc(r.get('acs_layer'))})</span></td>"
            f"<td>{_esc(r.get('auto_decision'))} <span class='mono text-secondary'>({_esc(r.get('auto_layer'))})</span></td>"
            f"<td>{ag_s}</td>"
            f"<td>{_esc(r.get('acs_ms'))}</td>"
            f"<td>{_esc(r.get('auto_ms'))}</td>"
            f"<td>{_esc(r.get('jev_ms'))}</td>"
            "</tr>"
        )
    parts.append("</tbody></table></div>")
    if summary.get("notes"):
        parts.append(f"<p class='text-secondary'>{_esc(summary['notes'])}</p>")
    parts.append("<details><summary>Methods appendix for this run</summary>")
    parts.append(f"<pre class='append mono'>{_esc(json.dumps(summary, indent=2)[:4000])}</pre></details>")
    parts.append("</section>\n")
    return "\n".join(parts)


_RUN_SECTION_RE = re.compile(
    r'<section class="run" data-run-id="[^"]+"[\s\S]*?</section>\s*',
    re.M,
)
_BLIND_SECTION_RE = re.compile(
    r'<section class="run" id="blind-[^"]+"[\s\S]*?</section>\s*',
    re.M,
)


def _extract_existing_runs(text: str) -> str:
    return "".join(_RUN_SECTION_RE.findall(text))


def _extract_existing_blinds(text: str) -> str:
    return "".join(_BLIND_SECTION_RE.findall(text))


def append_run(report_path: Path, summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    """Rewrite multi-page shell with latest numbers; prepend run history (newest first)."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    old_runs = ""
    old_blinds = ""
    blind_summary = None
    if report_path.exists():
        old_text = report_path.read_text(encoding="utf-8")
        old_runs = _extract_existing_runs(old_text)
        old_blinds = _extract_existing_blinds(old_text)
    runs_dir = report_path.parent / "runs"
    if runs_dir.is_dir():
        blind_files = sorted(runs_dir.glob("blind-*.summary.json"), reverse=True)
        if blind_files:
            try:
                blind_summary = json.loads(blind_files[0].read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                blind_summary = None
    shell = build_shell(summary, rows, blind_summary=blind_summary)
    section = render_run_section(summary, rows)
    if "<!--RUNS-->" not in shell:
        shell = shell.replace('<div id="runs">', '<div id="runs">\n<!--RUNS-->', 1)
    text = shell.replace("<!--RUNS-->", "<!--RUNS-->\n" + section + old_runs, 1)
    if "<!--BLIND-->" in text:
        text = text.replace("<!--BLIND-->", "<!--BLIND-->\n" + old_blinds, 1)
    elif old_blinds:
        text = text.replace("</body>", old_blinds + "\n</body>", 1)
    report_path.write_text(text, encoding="utf-8")


def rebuild_preserving_history(
    report_path: Path,
    summary: Dict[str, Any],
    rows: List[Dict[str, Any]],
    blind_summary: Optional[Dict[str, Any]] = None,
) -> None:
    """Full shell rebuild for template swaps; keep prior run + blind HTML sections."""
    old_runs = ""
    old_blinds = ""
    if report_path.exists():
        old_text = report_path.read_text(encoding="utf-8")
        old_runs = _extract_existing_runs(old_text)
        old_blinds = _extract_existing_blinds(old_text)
    if blind_summary is None and (report_path.parent / "runs").is_dir():
        blind_files = sorted((report_path.parent / "runs").glob("blind-*.summary.json"), reverse=True)
        if blind_files:
            try:
                blind_summary = json.loads(blind_files[0].read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
    shell = build_shell(summary, rows, blind_summary=blind_summary)
    rid = str(summary.get("run_id") or "")
    if rid and f'data-run-id="{html.escape(rid)}"' not in old_runs:
        old_runs = render_run_section(summary, rows) + old_runs
    text = shell.replace("<!--RUNS-->", "<!--RUNS-->\n" + old_runs, 1)
    text = text.replace("<!--BLIND-->", "<!--BLIND-->\n" + old_blinds, 1)
    report_path.write_text(text, encoding="utf-8")
