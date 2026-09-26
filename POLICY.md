# Agent Custom Setup — Policy

Standalone policy for this repository. Prefer this file over expanding PROJECT.md / AGENTS.md for ACS-specific registry rules.

## Authority

- **GitHub owns** accepted code, normative documents, issues (scope/lifecycle), and PR/merge delivery facts.
- **This repository (ACS) is source of truth** for registered agent setups. Desktop paths are **deploy mirrors**, not SoT.
- Sync direction: after an accepted merge, deploy **from ACS → Desktop** (and other listed mirrors). Do not treat Desktop edits as canonical until they are PR'd back into ACS.
- **Never commit secrets**: no API keys, tokens, cookies, `.env` contents, bak files, or credential dumps. Launchers may *read* secret files by absolute path at runtime; they must not embed values.
- **PR-only to `main`**: never commit directly to `main`. Branch per issue, push often, open a PR that links the owning issue. Do not force-push shared branches; do not merge your own work unless the user explicitly asks.

## Multi-setup registry

Every setup is a named, versioned module under:

```text
modules/<harness>/<setup-id>/v<semver>/
```

Examples:

- `modules/claude-code/inferhub-litellm/v0.2.0/`
- `modules/oh-my-pi/<setup-id>/v0.1.0/` (when contributed)

### Required identity fields (module + registry entry)

| Field | Meaning |
| --- | --- |
| `name` | Human-readable setup name |
| `purpose` | One-line purpose |
| `harness` | Runtime harness id (e.g. `claude-code`, `oh-my-pi`) |
| `created` | ISO date or date-time when the setup was first recorded |
| `updated` | ISO date or date-time of last accepted content change |
| `owning_issue` | GitHub issue URL or `#N` that owns this setup |
| `owning_agent` | Agent/writer note (e.g. `agent-custom-setup` / litellm bot) |
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
