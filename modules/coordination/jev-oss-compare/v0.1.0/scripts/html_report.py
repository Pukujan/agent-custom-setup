#!/usr/bin/env python3
"""Multi-page appendable HTML comparison report (CGM html-demo + HSW voice).

Pages via in-file nav: overview, method, pipeline, results, charts,
disagreements, how to append. Newest run sections stay prepended under history.
"""
from __future__ import annotations
import html, json, re
from pathlib import Path
from typing import Any, Dict, List, Optional

REPORT_NAME = "ACS Jev gate comparison"

SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
:root {{
  --fg:#1a1a1a; --muted:#555; --border:#d0d0d0; --ok:#1b5e20; --bad:#b71c1c;
  --bg:#fafafa; --card:#fff; --nav:#111; --accent:#0b57d0;
}}
* {{ box-sizing: border-box; }}
body {{ font-family: Georgia, "Times New Roman", serif; color:var(--fg); background:var(--bg); margin:0; line-height:1.45; }}
.topnav {{ position:sticky; top:0; z-index:20; background:var(--nav); color:#fff; display:flex; flex-wrap:wrap; gap:.35rem; padding:.55rem .75rem; }}
.topnav button {{
  font-family: system-ui, -apple-system, sans-serif; font-size:.82rem; border:1px solid #444;
  background:#222; color:#fff; padding:.35rem .65rem; border-radius:999px; cursor:pointer;
}}
.topnav button[aria-current="page"] {{ background:var(--accent); border-color:var(--accent); }}
.topnav button:focus-visible {{ outline:2px solid #fff; outline-offset:2px; }}
main {{ max-width: 56rem; margin: 0 auto; padding: 1.25rem 1rem 3rem; }}
h1,h2,h3 {{ font-family: system-ui, -apple-system, sans-serif; font-weight: 650; }}
h1 {{ font-size: 1.55rem; margin:.4rem 0 .25rem; }}
.lede {{ color: var(--muted); margin-bottom: 1.1rem; }}
.page {{ display:none; }}
.page.active {{ display:block; }}
.cards {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(10.5rem,1fr)); gap:.75rem; margin:1rem 0 1.4rem; }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:.85rem .9rem; }}
.card .label {{ font-family:system-ui,sans-serif; font-size:.78rem; color:var(--muted); text-transform:uppercase; letter-spacing:.03em; }}
.card .value {{ font-family:system-ui,sans-serif; font-size:1.45rem; font-weight:700; margin-top:.2rem; }}
.card .hint {{ font-size:.85rem; color:var(--muted); margin-top:.25rem; }}
table {{ border-collapse: collapse; width: 100%; font-size: .9rem; margin: .75rem 0 1.25rem; }}
th, td {{ border: 1px solid var(--border); padding: .4rem .55rem; text-align: left; vertical-align: top; }}
th {{ background: #eee; font-family: system-ui, sans-serif; }}
.ok {{ color: var(--ok); }}
.bad {{ color: var(--bad); }}
section.run {{ border-top: 2px solid var(--border); padding-top: 1rem; margin-top: 1.5rem; }}
details {{ margin: .5rem 0 1rem; }}
code, .mono {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .85rem; }}
.chart-wrap {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:1rem; margin:1rem 0; }}
.chart-wrap h3 {{ margin-top:0; font-size:1rem; }}
.mermaid {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:1rem; margin:1rem 0; overflow-x:auto; }}
footer {{ color: var(--muted); font-size: .85rem; margin-top: 2rem; }}
pre.append {{ background:#f3f3f3; border:1px solid var(--border); padding:.85rem; overflow-x:auto; border-radius:8px; }}
@media (max-width: 640px) {{
  .topnav {{ gap:.25rem; }}
  .topnav button {{ font-size:.75rem; padding:.3rem .5rem; }}
}}
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
</head>
<body>
<nav class="topnav" aria-label="Report pages">
  <button type="button" data-page="overview" aria-current="page">Overview</button>
  <button type="button" data-page="method">Method</button>
  <button type="button" data-page="pipeline">Pipeline</button>
  <button type="button" data-page="results">Results</button>
  <button type="button" data-page="charts">Charts</button>
  <button type="button" data-page="disagree">Disagreements</button>
  <button type="button" data-page="append">Append next run</button>
</nav>
<main>
<header>
<h1>{title}</h1>
<p class="lede">{lede}</p>
</header>

<section class="page active" id="page-overview" data-page="overview">
<h2>Overview</h2>
{overview}
</section>

<section class="page" id="page-method" data-page="method">
<h2>How we compared</h2>
{method}
<h3>What we kept and what we skipped</h3>
{decision}
</section>

<section class="page" id="page-pipeline" data-page="pipeline">
<h2>Pipeline</h2>
<p>Two short diagrams. ACS prefers fewer, simpler Mermaid charts.</p>
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
</section>

<section class="page" id="page-results" data-page="results">
<h2>Results in plain English</h2>
{results}
</section>

<section class="page" id="page-charts" data-page="charts">
<h2>Charts</h2>
{charts}
</section>

<section class="page" id="page-disagree" data-page="disagree">
<h2>Where the lanes disagreed</h2>
{disagree}
</section>

<section class="page" id="page-append" data-page="append">
<h2>How to append the next run</h2>
{append_howto}
<section id="runs">
<h3>Run history</h3>
<p class="lede">Newest sections appear at the top. Each run keeps its own table so later benches do not overwrite earlier numbers.</p>
<!--RUNS-->
</section>
</section>

<footer>
<p>Built with ACS CGM html-demo structure and human-sounding-writing voice. Live path uses OpenRouter <span class="mono">typesafe/jev-1.13</span> (fast Jev OK). Secrets never printed. Ultrafast skipped. No Redis.</p>
</footer>
</main>
<script>
(function () {{
  const buttons = Array.from(document.querySelectorAll('.topnav button'));
  const pages = Array.from(document.querySelectorAll('.page'));
  function show(id) {{
    pages.forEach(p => p.classList.toggle('active', p.dataset.page === id));
    buttons.forEach(b => b.setAttribute('aria-current', b.dataset.page === id ? 'page' : 'false'));
    if (location.hash !== '#' + id) history.replaceState(null, '', '#' + id);
  }}
  buttons.forEach(b => b.addEventListener('click', () => show(b.dataset.page)));
  const initial = (location.hash || '#overview').slice(1);
  show(buttons.some(b => b.dataset.page === initial) ? initial : 'overview');
  if (window.mermaid) {{ mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }}); }}
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
            "<p>No compare run has been appended yet. Harvest packs, run "
            "<span class='mono'>compare_run.py --cap 60 --live --append-html</span>, "
            "then reopen this file.</p>"
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
<div class="cards">
  <div class="card"><div class="label">Packs compared</div><div class="value">{n}</div><div class="hint">Fish + fixtures + harvested Claude tool uses</div></div>
  <div class="card"><div class="label">Agreement rate</div><div class="value ok">{_esc(agree_pct)}%</div><div class="hint">{agree} agree · {disagree} differ</div></div>
  <div class="card"><div class="label">Missed denies (FN)</div><div class="value">{_esc(summary.get('fn_vs_gold'))}</div><div class="hint">Gold said deny, ACS did not</div></div>
  <div class="card"><div class="label">False denies (FP)</div><div class="value">{_esc(summary.get('fp_vs_gold'))}</div><div class="hint">Gold said allow, ACS denied</div></div>
  <div class="card"><div class="label">Jev latency p50</div><div class="value">{_esc(_ms(summary.get('p50_jev_ms') or summary.get('median_jev_ms')))}</div><div class="hint">Half of live Jev calls were this fast or faster</div></div>
  <div class="card"><div class="label">Jev latency p95</div><div class="value">{_esc(_ms(summary.get('p95_jev_ms')))}</div><div class="hint">95th percentile live Jev call</div></div>
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
        "<table><thead><tr><th>What we measured</th><th>Value</th><th>Meaning</th></tr></thead><tbody>",
        f"<tr><td>Pack count</td><td class='mono'>{n}</td><td>How many tool packs both lanes saw</td></tr>",
        f"<tr><td>Agree</td><td class='mono ok'>{agree} ({_pct(agree, n)})</td><td>ACS and auto-mode returned the same decision</td></tr>",
        f"<tr><td>Disagree</td><td class='mono'>{disagree} ({_pct(disagree, n)})</td><td>Lanes returned different decisions</td></tr>",
        f"<tr><td>False negatives vs gold</td><td class='mono'>{_esc(summary.get('fn_vs_gold'))}</td><td>Gold deny/block, ACS did not deny</td></tr>",
        f"<tr><td>False positives vs gold</td><td class='mono'>{_esc(summary.get('fp_vs_gold'))}</td><td>Gold allow, ACS denied</td></tr>",
        f"<tr><td>Jev latency p50</td><td class='mono'>{_esc(_ms(summary.get('p50_jev_ms') or summary.get('median_jev_ms')))}</td><td>Median live Jev round-trip</td></tr>",
        f"<tr><td>Jev latency p95</td><td class='mono'>{_esc(_ms(summary.get('p95_jev_ms')))}</td><td>Slow-tail live Jev round-trip</td></tr>",
        f"<tr><td>ACS lane p50 / p95</td><td class='mono'>{_esc(_ms(summary.get('p50_acs_ms')))} / {_esc(_ms(summary.get('p95_acs_ms')))}</td><td>End-to-end ACS pack latency</td></tr>",
        f"<tr><td>Wall clock</td><td class='mono'>{_esc(_ms(summary.get('wall_ms')))}</td><td>Whole compare with {_esc(summary.get('workers'))} workers</td></tr>",
        f"<tr><td>Mode</td><td class='mono'>{'live Jev' if summary.get('live') else 'mock only'}</td><td>Model {_esc(summary.get('model') or 'typesafe/jev-1.13')}</td></tr>",
        "</tbody></table>",
    ]
    if summary.get("notes"):
        parts.append(f"<p>{_esc(summary['notes'])}</p>")
    return "\n".join(parts)


def _disagree_block(rows: List[Dict[str, Any]]) -> str:
    bad = [r for r in rows if not r.get("agree")]
    if not bad:
        return "<p>No disagreements in the newest run. Both lanes matched on every pack.</p>"
    parts = [
        f"<p>{len(bad)} pack(s) where ACS and auto-mode differed. Useful for triage, not a scoreboard.</p>",
        "<table><thead><tr><th>Pack</th><th>Gold</th><th>ACS</th><th>Auto-mode</th><th>Jev ms</th></tr></thead><tbody>",
    ]
    for r in bad:
        parts.append(
            "<tr>"
            f"<td class='mono'>{_esc(r.get('id'))}</td>"
            f"<td>{_esc(r.get('gold') or '—')}</td>"
            f"<td>{_esc(r.get('acs_decision'))} <span class='mono'>({_esc(r.get('acs_layer'))})</span></td>"
            f"<td>{_esc(r.get('auto_decision'))} <span class='mono'>({_esc(r.get('auto_layer'))})</span></td>"
            f"<td>{_esc(r.get('jev_ms'))}</td>"
            "</tr>"
        )
    parts.append("</tbody></table>")
    return "\n".join(parts)


def _charts_markup(summary: Optional[Dict[str, Any]], rows: List[Dict[str, Any]]) -> str:
    if not summary:
        return "<p>Charts appear after the first appended run.</p>"
    agree = int(summary.get("agree") or 0)
    disagree = int(summary.get("disagree") or 0)
    # latency series: sample up to 40 points for readability
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
<div class="chart-wrap">
  <h3>ACS and auto-mode matched on most packs</h3>
  <canvas id="agreeChart" height="120" aria-label="Agree versus disagree counts"></canvas>
</div>
<div class="chart-wrap">
  <h3>Jev and ACS latency stayed in the low hundreds of milliseconds</h3>
  <canvas id="latChart" height="140" aria-label="Latency per pack"></canvas>
  <p class="lede">First {nshow} packs shown so the line stays readable. Full table lives under Append next run → run history.</p>
</div>
<script type="application/json" id="chart-data">{payload}</script>
"""



def _chart_boot() -> str:
    return """
  const raw = document.getElementById('chart-data');
  if (!raw || !window.Chart) return;
  let data;
  try { data = JSON.parse(raw.textContent); } catch (e) { return; }
  const agreeEl = document.getElementById('agreeChart');
  const latEl = document.getElementById('latChart');
  if (agreeEl) {
    new Chart(agreeEl, {
      type: 'bar',
      data: {
        labels: ['Agree', 'Disagree'],
        datasets: [{ label: 'Packs', data: [data.agree, data.disagree],
          backgroundColor: ['#2e7d32', '#c62828'] }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false }, title: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
      }
    });
  }
  if (latEl) {
    new Chart(latEl, {
      type: 'line',
      data: {
        labels: data.labels,
        datasets: [
          { label: 'Jev ms', data: data.jev, borderColor: '#0b57d0', tension: 0.2, pointRadius: 2 },
          { label: 'ACS ms', data: data.acs, borderColor: '#6a1b9a', tension: 0.2, pointRadius: 2 }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'bottom' } },
        scales: { x: { ticks: { maxRotation: 60, minRotation: 30, autoSkip: true, maxTicksLimit: 12 } },
                  y: { beginAtZero: true, title: { display: true, text: 'milliseconds' } } }
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


def build_shell(
    summary: Optional[Dict[str, Any]] = None,
    rows: Optional[List[Dict[str, Any]]] = None,
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
<table>
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
</table>
<p>Claude and Kilo keep ACS adapters live. HOTLOAD default stays ACS pin → pack → Jev.</p>
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
        append_howto=_append_howto(),
        chart_boot=_chart_boot(),
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
        f"<h3>Run {rid}</h3>",
        f"<p>{when}. {n} packs, {live}. Agreement ACS vs auto-mode: "
        f"<strong class='ok'>{agree} agree ({_esc(agree_pct)}%)</strong>, {disagree} differ. "
        f"Against gold where present: FN={fn}, FP={fp}."
        + (f" Jev p50 {_esc(_ms(p50))}, p95 {_esc(_ms(p95))}." if p50 is not None or p95 is not None else "")
        + "</p>",
        "<table><thead><tr>"
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
            f"<td>{_esc(r.get('acs_decision'))} <span class='mono'>({_esc(r.get('acs_layer'))})</span></td>"
            f"<td>{_esc(r.get('auto_decision'))} <span class='mono'>({_esc(r.get('auto_layer'))})</span></td>"
            f"<td>{ag_s}</td>"
            f"<td>{_esc(r.get('acs_ms'))}</td>"
            f"<td>{_esc(r.get('auto_ms'))}</td>"
            f"<td>{_esc(r.get('jev_ms'))}</td>"
            "</tr>"
        )
    parts.append("</tbody></table>")
    if summary.get("notes"):
        parts.append(f"<p>{_esc(summary['notes'])}</p>")
    parts.append("<details><summary>Methods appendix for this run</summary>")
    parts.append(f"<pre class='mono'>{_esc(json.dumps(summary, indent=2)[:4000])}</pre></details>")
    parts.append("</section>\n")
    return "\n".join(parts)


_RUN_SECTION_RE = re.compile(
    r'<section class="run" data-run-id="[^"]+"[\s\S]*?</section>\s*',
    re.M,
)


def _extract_existing_runs(text: str) -> str:
    return "".join(_RUN_SECTION_RE.findall(text))


def append_run(report_path: Path, summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    """Rewrite multi-page shell with latest numbers; prepend run history (newest first)."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    old_runs = ""
    if report_path.exists():
        old_runs = _extract_existing_runs(report_path.read_text(encoding="utf-8"))
    shell = build_shell(summary, rows)
    section = render_run_section(summary, rows)
    if "<!--RUNS-->" not in shell:
        shell = shell.replace('<section id="runs">', '<section id="runs">\n<!--RUNS-->', 1)
    text = shell.replace("<!--RUNS-->", "<!--RUNS-->\n" + section + old_runs, 1)
    report_path.write_text(text, encoding="utf-8")
