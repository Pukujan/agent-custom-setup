#!/usr/bin/env python3
"""Appendable HTML comparison report (CGM html-demo + HSW voice).

Human-sounding: concrete opening, verified numbers, restrained bold, no brochure.
New runs append <section data-run-id> under #runs.
"""
from __future__ import annotations
import html, json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPORT_NAME = "ACS Jev gate comparison"

SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
:root {{ --fg:#1a1a1a; --muted:#555; --border:#d0d0d0; --ok:#1b5e20; --bad:#b71c1c; --bg:#fafafa; }}
body {{ font-family: Georgia, "Times New Roman", serif; color:var(--fg); background:var(--bg); margin:0; line-height:1.45; }}
main {{ max-width: 52rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; }}
h1,h2,h3 {{ font-family: system-ui, -apple-system, sans-serif; font-weight: 650; }}
h1 {{ font-size: 1.6rem; margin-bottom: .25rem; }}
.lede {{ color: var(--muted); margin-bottom: 1.5rem; }}
table {{ border-collapse: collapse; width: 100%; font-size: .92rem; margin: .75rem 0 1.25rem; }}
th, td {{ border: 1px solid var(--border); padding: .4rem .55rem; text-align: left; vertical-align: top; }}
th {{ background: #eee; font-family: system-ui, sans-serif; }}
.ok {{ color: var(--ok); }}
.bad {{ color: var(--bad); }}
section.run {{ border-top: 2px solid var(--border); padding-top: 1rem; margin-top: 1.5rem; }}
details {{ margin: .5rem 0 1rem; }}
code, .mono {{ font-family: ui-monospace, Menlo, Consolas, monospace; font-size: .85rem; }}
footer {{ color: var(--muted); font-size: .85rem; margin-top: 2rem; }}
</style>
</head>
<body>
<main>
<header>
<h1>{title}</h1>
<p class="lede">{lede}</p>
</header>
<section id="method">
<h2>How we compared</h2>
{method}
</section>
<section id="decision">
<h2>What we kept and what we skipped</h2>
{decision}
</section>
<section id="runs">
<h2>Runs</h2>
<p class="lede">Newest sections appear at the top. Each run keeps its own table so later benches do not overwrite earlier numbers.</p>
<!--RUNS-->
</section>
<footer>
<p>Generated with ACS CGM html-demo structure and human-sounding-writing voice. Live path uses OpenRouter <span class="mono">typesafe/jev</span>; secrets never printed. Ultrafast skipped. No Redis.</p>
</footer>
</main>
</body>
</html>
"""

def _esc(s: Any) -> str:
    return html.escape(str(s) if s is not None else "")

def build_shell() -> str:
    lede = (
        "On the Fish hosted-vs-selfhost fixture, ACS mock denied the self-host clone before any model call. "
        "This page tracks whether an auto-mode-shaped hard-deny peer agrees, and what real Jev says when we ask it."
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
    return SHELL.format(title=_esc(REPORT_NAME), lede=lede, method=method, decision=decision)

def render_run_section(summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
    rid = _esc(summary.get("run_id"))
    when = _esc(summary.get("started_at"))
    n = summary.get("n_packs", len(rows))
    agree = summary.get("agree", 0)
    disagree = summary.get("disagree", 0)
    fn = summary.get("fn_vs_gold", 0)
    fp = summary.get("fp_vs_gold", 0)
    live = "live Jev" if summary.get("live") else "mock only"
    med = summary.get("median_jev_ms")
    parts = [
        f'<section class="run" data-run-id="{rid}" id="run-{rid}">',
        f"<h3>Run {rid}</h3>",
        f"<p>{when}. {n} packs, {live}. Agreement ACS vs auto-mode: "
        f"<strong class='ok'>{agree} agree</strong>, {disagree} differ. "
        f"Against gold where present: FN={fn}, FP={fp}."
        + (f" Median Jev latency {med} ms." if med is not None else "")
        + "</p>",
        "<table><thead><tr>"
        "<th>Pack</th><th>Gold</th><th>ACS</th><th>Auto-mode</th><th>Agree</th>"
        "<th>ACS ms</th><th>Auto ms</th><th>Jev ms</th></tr></thead><tbody>",
    ]
    for r in rows:
        ag = r.get("agree")
        ag_s = f"<span class='ok'>yes</span>" if ag else f"<span class='bad'>no</span>"
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

def append_run(report_path: Path, summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if not report_path.exists():
        report_path.write_text(build_shell(), encoding="utf-8")
    text = report_path.read_text(encoding="utf-8")
    section = render_run_section(summary, rows)
    if "<!--RUNS-->" not in text:
        text = text.replace('<section id="runs">', '<section id="runs">\n<!--RUNS-->', 1)
    # Newest first
    text = text.replace("<!--RUNS-->", "<!--RUNS-->\n" + section, 1)
    report_path.write_text(text, encoding="utf-8")
