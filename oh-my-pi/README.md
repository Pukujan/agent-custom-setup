# oh-my-pi module

Versioned setup for [omp](https://github.com/can1306/oh-my-pi) (oh-my-pi coding agent):
advisor roster, JEV judge wiring, and the `jev-court` advisor-adjudication extension.

Install: copy `config/*` into `~/.omp/agent/` (as `config.yml`, `models.yml`,
`WATCHDOG.yml`, `jev-court.json`) and `extensions/jev-court.ts` into
`~/.omp/agent/extensions/`. Put real secret values in `~/.omp/agent/.env`
(see `config/.env.example` — the file itself is never committed here or there).

## What this module provides

| Surface | Purpose |
|---|---|
| `config/models.yml` | Providers + the **judge** role pointed at TypeSafe JEV (`openrouter-jev/typesafe/jev-1.13`, OpenRouter decisions API). `apiKey` fields are variable NAMES resolved from `~/.omp/agent/.env`. |
| `config/WATCHDOG.yml` | Advisor roster: `research` (external validation critic) + `scope` (scope-blowout gate), severity rubrics, and the rule that plan-vs-research disputes go to JEV for tie-break. |
| `config/config.yml` | Model roles + `advisor.enabled`, `advisor.syncBacklog: 1` (bounds advisor staleness against the primary transcript). |
| `extensions/jev-court.ts` | Mechanical pipeline: tails advisor transcript JSONL → chunks each `advise` note with its provenance + primary digest → POSTs to JEV → routes by risk-tiered confidence threshold (act/ignore/insufficient_evidence). Fail-open on court errors; decisions remembered so advisor resets cannot resurrect adjudicated claims. Slash command `/jev` shows status/ledger. |

## Verified behavior (2026-09-25)

- Live JEV adjudication of 3 real advisor notes from the PCM project session:
  `act@0.92`, `act@0.94`, `act@0.96`; a synthetic trivia note: `ignore@0.98`.
- Cost per adjudication ≈ $0.00005.
- Root cause fixed here: the previously configured judge selector
  `openrouter/~typesafe/jev-latest` failed 401 on every candidate
  (`provider proxy resolved, source:none`), so JEV had never contributed a decision.
- Advisor tool grant corrected: `web_fetch` is not a builtin name (was dropped
  with warning 49×); roster now grants `web_search`.

## Files intentionally NOT in this repo

- `~/.omp/agent/.env` — live secrets.
- `agent.db` / `models.db` / `history.db` — credentials, OAuth tokens, transcripts.
- Session artifacts (`sessions/`, `blobs/`, `logs/`) — user data.
