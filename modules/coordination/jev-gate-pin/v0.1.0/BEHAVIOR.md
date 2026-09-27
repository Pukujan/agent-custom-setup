# BEHAVIOR — jev-gate-pin (normative stub)

Owning issue: [#17](https://github.com/Pukujan/agent-custom-setup/issues/17).

Architecture cite: knowledge pack `docs/knowledge/jev-architecture-gate-pin-compaction-fish.md` (id `acs-jev-architecture-gate-pin-compaction-fish`); knowledge [#15](https://github.com/Pukujan/agent-custom-setup/issues/15) / PR [#16](https://github.com/Pukujan/agent-custom-setup/pull/16).

## When the gate fires

Fire on **risk-class** tool proposals first (not every file read):

- `pip` / package install / lockfile edits
- External API / SDK **first-use** or bump
- Clone / install of external speech or model stacks
- Other install / external-SDK class actions called out in the brief

Low-risk local reads/edits may skip the judge later (lexical/BM25); v0.1 mock still returns `allow` for non-conflicting cases.

## Outcomes

| Decision | Meaning |
| --- | --- |
| **allow** | Tool may proceed |
| **deny** | Block tool; log event; do not run |
| **escalate** | Human / boss; fail closed when judge unavailable |

## Mock judge (default / CI)

Fish-class rules:

- Brief/corrections say **hosted API** and proposed tool is **clone / pip install fish-speech / self-host** → **deny**
- Proposed tool is **fish.audio hosted API** call → **allow**

## InferHub / JEV judge stub

`--judge inferhub` does **not** call paid APIs unless env is clearly configured (`JEV_INFERHUB_GATE_ENABLED` + `JEV_INFERHUB_ENDPOINT`). If not configured or not implemented → **escalate** (fail closed). Prefer `--judge mock` for CI.

## Ultrafast

**Browser only.** Must not act as API researcher or gate judge.

## Does not replace research checklist

This module does **not** replace the external research paperwork gate ([#13](https://github.com/Pukujan/agent-custom-setup/issues/13) / [#14](https://github.com/Pukujan/agent-custom-setup/pull/14)). Checklist provenance remains mechanical; this gate is a tool-veto / constraint-pin path.

## Secrets

Never put API keys, tokens, `.env` contents, or cookies in packages, fixtures, logs, or commits. `log_event` redacts obvious secret-looking strings; callers must still avoid pasting secrets into briefs.
