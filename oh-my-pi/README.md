# oh-my-pi module

Versioned setup for [omp](https://github.com/can1306/oh-my-pi) (oh-my-pi coding agent):
advisor roster, JEV judge wiring, and the `jev-court` advisor-adjudication extension.

Install: copy `config/*` into `~/.omp/agent/` (as `config.yml`, `models.yml`,
`WATCHDOG.yml`, `jev-court.json`) and `extensions/jev-court.ts` +
`extensions/loop-guard.ts` into `~/.omp/agent/extensions/`. Put real secret values
in `~/.omp/agent/.env` (see `config/.env.example` — the file itself is never
committed here or there).

## What this module provides

| Surface | Purpose |
|---|---|
| `config/models.yml` | Providers + the **judge** role pointed at TypeSafe JEV (`openrouter-jev/typesafe/jev-1.13`, OpenRouter decisions API). `apiKey` fields are variable NAMES resolved from `~/.omp/agent/.env`. |
| `config/WATCHDOG.yml` | Advisor roster: `research` (external-validation critic; silence-first, budget 1/update) + `scope` (DISABLED — #35 blocker-factory severity rule), severity rubrics, and the rule that plan-vs-research disputes go to JEV for tie-break. |
| `config/config.yml` | Model roles + advisor storm bounds (`enabled`, `syncBacklog: "3"` — quoted, string enum; `immuneTurns: 6`, `maxNotesPerUpdate: 2`, `goal.continuationModes: []`, `todo.remindersMax: 1`). |
| `extensions/jev-court.ts` | **v2 (opt-in, `enabled: false` by default)**: tails advisor transcript JSONL → adjudicates each `advise` note with its provenance + primary digest via JEV → routes by risk-tiered thresholds. v2 contract: fail-QUIET (court down → nothing injected), per-minute + per-session delivery budgets, never `steer`, `nextTurn` when idle (no wake-ups), owner-stop suppression, transcript reconciliation (notes already visible natively are not re-sent), re-raise signature reuse, durable per-decision records rehydrated from the session branch. Verdict wording is non-mandatory: no acknowledgement turn required. |
| `extensions/loop-guard.ts` | Delivery hygiene for channels the court doesn't own: marks replayed `[async-result]` background announcements in the provider message list (in-place marking; no removals, tool-pairing intact), and flags `task` results that echo the subagent's own tool-call JSON via passive `additionalContext` ("implement directly or re-spawn once; no audit turn"). Observation-only: never blocks, sends, or steers. `/loopguard` shows counters. |

## Verified behavior (2026-09-25)

- Live JEV adjudication of 3 real advisor notes from the PCM project session:
  `act@0.92`, `act@0.94`, `act@0.96`; a synthetic trivia note: `ignore@0.98`.
- Cost per adjudication ≈ $0.00005.
- Root cause fixed here: the previously configured judge selector
  `openrouter/~typesafe/jev-latest` failed 401 on every candidate
  (`provider proxy resolved, source:none`), so JEV had never contributed a decision.
- Advisor tool grant corrected: `web_fetch` is not a builtin name (was dropped
  with warning 49×); roster now grants `web_search`.

## Loop hardening (2026-09-29 — issues #35/#37)

Measured cause of "omp loops on injected advisories, sessions never finish": in
the #35 session the harness emission guard accepted ~11 native advisory cards from
94 advisor notes, while jev-court v1 injected **83** messages — bypassing
`maxNotesPerUpdate`/`immuneTurns`/stop-suppression, `steer`-interrupting or
waking idle sessions (`aside` starts a turn when idle), fail-OPENING court errors
as `act`, delivering its least-confident verdict (`insufficient_evidence`)
unthresholded, and keeping its dedupe memory in RAM only (the persisted ledger was
never read back). Separately, `advisor.syncBacklog: 1` (bare YAML number) fails the
`off|1|3|5` string enum and silently resolved to `off` — the documented staleness
fix was never in effect (verify with `omp config get advisor.syncBacklog`).

Fixes here: jev-court v2 (above), `loop-guard`, roster hardening (silence-first
instructions, `maxNotesPerUpdate: 1`, `scope` advisor disabled pending hardened
severity rules), and `config.yml` storm keys (`syncBacklog: "3"` quoted,
`immuneTurns: 6`, `maxNotesPerUpdate: 2`, `goal.continuationModes: []`,
`todo.remindersMax: 1`).

Verified 2026-09-29: real jev-court v2 + loop-guard code replayed against the real
#35 fixture (94 notes, primary transcript) under mocked harness surfaces — 32/32
assertions: v1's 83-message storm → **0 injections** (94/94 reconciled as
`dup_in_transcript`); fresh-transcript run capped 2/min; zero `steer`/idle wakes;
reworded re-raises reuse prior verdicts with no fetch; rehydration blocks
re-adjudication after restart; no-key mode injects nothing (one warning only);
post-stop notes suppressed except high-risk; replay marking is pairing-safe; echo
detection never mutates tool content. Extensions additionally load cleanly in the
installed v18.4.4 harness (`omp -p` scratch run, no load diagnostics).

Upstream residue (not reachable from this module): the async-result *wake* itself
is harness-owned (marking happens per-request), and `todo_reminder`/`goal_updated`
are notification-only events — reminder suppression uses the config levers above.

## Files intentionally NOT in this repo

- `~/.omp/agent/.env` — live secrets.
- `agent.db` / `models.db` / `history.db` — credentials, OAuth tokens, transcripts.
- Session artifacts (`sessions/`, `blobs/`, `logs/`) — user data.
