# BEHAVIOR — jev-oss-compare

1. ACS gates remain HOTLOAD default (deterministic pin → gather pack → Jev/mock).
2. This module is eval/compare only; Claude and Kilo live adapters stay ACS.
3. Auto-mode peer: hard-deny first (never Jev), then user deny/allow, safe fast-path, then Jev/mock.
4. jev-gate stub: post-run criteria only; never PreToolUse.
5. Live Jev via OpenRouter `typesafe/jev-1.13` when `ACS_JEV_LIVE=1` + key; mock otherwise.
6. HTML report appends a new `<section data-run-id>` per bench; CGM html-demo sections + HSW voice (default ON, not opt-in). HTML is Tabler dark-only (data-bs-theme=dark / color-scheme:dark only). Before GitHub Pages / publish: `python "$CGM_ROOT/scripts/verify_hsw_applied.py" --root "$CGM_ROOT" --mode acs-html --html reports/jev-oss-compare.html` (wired in `html_report.append_run` / `rebuild_preserving_history`); fix jargon/tool-dump fails.
7. Skip ultrafast. No Redis. Never print secrets.
