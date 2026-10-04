# Agent Custom Setup — Policy

Standalone policy for this repository. Prefer this file over expanding PROJECT.md / AGENTS.md for ACS-specific coordination rules.

## What ACS owns

ACS owns **execution coordination** for multi-agent work on one repository: turning logged tickets into workable tasks, decomposing them, and keeping several agents on one repo honest. The product it ships is the **multi-agent hotload pack** (`modules/coordination/multi-agent-hotload/`). ACS does **not** log tickets (OIO), write prose (CGM), own continuity (PCM), own versions (train), or decide between agents (JEV, parked in `jev-dump`). See PROJECT.md for the full layer table.

## Authority

- **GitHub owns** accepted code, normative documents, issues (scope/lifecycle), and PR/merge delivery facts.
- **This repository (ACS) is source of truth** for the multi-agent hotload pack. Desktop paths are **deploy mirrors**, not SoT.
- Sync direction: after an accepted merge, deploy **from ACS → mirrors**. Do not treat mirror edits as canonical until they are PR'd back into ACS.
- **Never commit secrets**: no API keys, tokens, cookies, `.env` contents, bak files, or credential dumps.
- **PR-only to `main`**: never commit directly to `main`. Branch per issue, push often, open a PR that links the owning issue. Do not force-push shared branches; do not merge your own work unless the user explicitly asks.

## Module registry

Every module is a named, versioned directory under:

```text
modules/<area>/<module-id>/v<semver>/
```

ACS ships exactly one module today:

- `modules/coordination/multi-agent-hotload/v0.1.0/` — the multi-agent hotload pack.

### Required identity fields (module + registry entry)

| Field | Meaning |
| --- | --- |
| `name` | Human-readable module name |
| `purpose` | One-line purpose |
| `harness` | Runtime harness id (e.g. `coordination`) |
| `created` | ISO date or date-time when the module was first recorded |
| `updated` | ISO date or date-time of last accepted content change |
| `owning_issue` | GitHub issue URL or `#N` that owns this module |
| `owning_agent` | Agent/writer note |
| `deploy_mirrors` | Absolute paths (or labeled targets) that receive deployed copies |
| `version` | Semver for this module directory (`v<semver>` folder name must match) |
| `status` | `draft` \| `active` \| `deprecated` \| `unknown` |

Schemas: `schemas/module.schema.json`, `schemas/registry.schema.json`. Index: `registry.json`.

## CI and branch protection

Required CI checks and branch protection on `main` are **mandatory when GitHub Actions capacity allows**. Tracked in:

- Issue [#5](https://github.com/Pukujan/agent-custom-setup/issues/5) — ACS-0002 CI gates + branch protection + auto-merge
- PR [#6](https://github.com/Pukujan/agent-custom-setup/pull/6) — required ci gates + marker sync

Until those land and are verified live, treat missing/failed/skipped/unverified gates as fail-closed for *claiming delivery complete*; still use PR-only workflow.

## Coordination

- One primary writer per task branch. Prefer **new files** under `modules/`, `schemas/`, `POLICY.md`, and `registry.json` when another agent may touch shared docs.
- Minimize edits to `PROJECT.md` / `AGENTS.md` unless PCM markers require it.
- Re-read live issues and current base before resuming. Link PRs with `Refs #N` for progress-only; use closing keywords only when merge should complete the issue.

### Working-repo scope (hotload adopters)

Adopters using ACS / the multi-agent hotloader may only write code (commits, branches, PRs, claims, boss actions) on **their own working repo** — the GitHub repo they hot-loaded into. They **must not** push, open PRs, claim, ACCEPT/REJECT, or otherwise mutate other projects' repositories. **Exception:** they may report findings to another repo's issue log **only** as a proposed ticket (open/comment a Proposal-style issue) — issue-log only; no code, claim, PR, or boss actions on the foreign repo. Normative detail: `modules/coordination/multi-agent-hotload/v0.1.0/BEHAVIOR.md`.

### External research gate (hotload adopters)

Binding selective research (not always-on): MUST on first use / introduce, version bump, or install/runtime/API failure of an external OSS/SDK/CLI/API/framework/cloud surface; MUST NOT for trivial in-repo edits of already-known patterns. Exact version + official docs for that version; provenance checklist on the issue/PR. Normative detail: modules/coordination/multi-agent-hotload/v0.1.0/BEHAVIOR.md.
