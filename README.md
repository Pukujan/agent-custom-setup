# Agent Custom Setup

![Registry icon](assets/registry-icon.svg)

> **Durable, reviewable agent setups — so a fresh session can resume without living in one chat's memory.**

## Why this exists

An agent setup is usually invisible work: a launcher, a roster of roles, a lease rule, a `.env` full of keys. It lives in whatever session built it. When that session ends, the **next reader inherits nothing they can trust**.

ACS turns that invisible state into **versioned modules** with an evidence trail, so humans and agents can resume from the repository alone.

## What this project is

**agent-custom-setup** (ACS) is a private registry of customized agent setups. It is for operators who keep agent configuration on a personal machine, for fresh agent sessions that must cold-start from git, and for authors adding new harness modules.

It is **not** a secrets vault (keys never enter git), not a hosted agent platform, and not a guarantee that any setup works on your machine unchanged.

**Status at a glance:** ACS is source of truth for registered setups; Desktop paths are deploy mirrors. Policy lives in [`POLICY.md`](POLICY.md); the live index is [`registry.json`](registry.json).

## What you can make or use

- **A versioned module registry** under `modules/<harness>/<setup-id>/v<semver>/`, indexed by [`registry.json`](registry.json) with temporal metadata and deploy mirrors.
- **InferHub Claude Code (LiteLLM)** @ `0.2.0` — sanitized launcher that seats main/advisor through local LiteLLM; keys stay in gitignored `.env` at runtime. Path: [`modules/claude-code/inferhub-litellm/v0.2.0/`](modules/claude-code/inferhub-litellm/v0.2.0/).
- **Multi-agent hotload coordination** @ `0.1.0` — install surface that wires continuity helpers + this coordination runtime (join-order roles, boss lease, claim queue, agent-less watchdog, proposals → claim → PR). Path: [`modules/coordination/multi-agent-hotload/v0.1.0/`](modules/coordination/multi-agent-hotload/v0.1.0/). Start at [`HOTLOAD.md`](modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md).
- **A no-secrets template pattern** — every provider key is referenced by environment-variable *name* only; real values live outside this repository.

## How it works

1. A task begins as a **GitHub issue** — issues own scope, acceptance, and lifecycle (`AGENTS.md`).
2. Work happens on a **task branch**; increments land through PR + review into `main` (PR-only; no direct pushes to `main`).
3. Accepted setups are recorded under `modules/…` and listed in **`registry.json`**.
4. After merge, deploy **from ACS → Desktop** (or other listed mirrors). Desktop edits are not canonical until PR'd back.
5. For multi-agent work, agents **hot-load** the coordination pack: read ACS policy → pin required continuity helpers → run this runtime. Install is complete only when `hotload_check` passes on the working repo.

**Hotload product surface (coordination pack):**

| Piece | What it does |
| --- | --- |
| Join-order roles | First agents fill boss/worker slots from assignment schema |
| Boss lease | Default **30 minutes** (range **15–120**); vacancy opens the claim queue |
| Claim queue | FIFO on the GitHub-canonical claim; returning boss joins the **end** |
| Watchdog | Agent-less ~**10m** liveness / nudge / write-`vacant` — not failover |
| Proposals → claim → PR | Progress stays on GitHub; no out-of-band DMs for lease loss |

Working-repo scope: adopters may write code only on the repo they hot-loaded into; foreign repos get proposal-style issue comments only. Details: [`BEHAVIOR.md`](modules/coordination/multi-agent-hotload/v0.1.0/BEHAVIOR.md).

**Cold-start example:** clone ACS, open [`POLICY.md`](POLICY.md) and [`registry.json`](registry.json) to see which modules are active, then from a working repo that points at this checkout run `python modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py` and fix until it passes.

## Evidence and boundaries

| Claim | Status | Supports | Limits | Source |
|---|---|---|---|---|
| ACS registry indexes versioned modules with temporal metadata | shipped | `registry.json` lists active modules with paths and versions | Index accuracy depends on PR discipline | [registry.json @ 7455df5](https://github.com/Pukujan/agent-custom-setup/blob/7455df515712fa4c18931a099cacddcd861528ee/registry.json) |
| InferHub LiteLLM Claude Code launcher sealed at 0.2.0 | shipped | Module tree + secrets policy (env names only) | Needs local LiteLLM + runtime `.env` | [inferhub-litellm v0.2.0 @ 7455df5](https://github.com/Pukujan/agent-custom-setup/tree/7455df515712fa4c18931a099cacddcd861528ee/modules/claude-code/inferhub-litellm/v0.2.0) |
| Multi-agent hotload pack registered @ 0.1.0 with lease/queue/watchdog rules | shipped (merged PR [#12](https://github.com/Pukujan/agent-custom-setup/pull/12)) | Pack docs, schema, `hotload_check`, tests on `main` | Does not prove every adopter has run the check | [HOTLOAD.md @ 7455df5](https://github.com/Pukujan/agent-custom-setup/blob/7455df515712fa4c18931a099cacddcd861528ee/modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md) |
| ACS is SoT; Desktop is deploy mirror; no secrets in git | shipped (policy) | POLICY.md authority + secrets rules | Policy text, not a runtime enforcer | [POLICY.md @ 7455df5](https://github.com/Pukujan/agent-custom-setup/blob/7455df515712fa4c18931a099cacddcd861528ee/POLICY.md) |
| External research gate for hotload adopters | planned | Open PR proposes binding research gate | Not merged; do not treat as shipped | [PR #14](https://github.com/Pukujan/agent-custom-setup/pull/14) |
| JEV architecture knowledge pack | planned | Open PR proposes knowledge pack module | Not merged; not on `main` | [PR #16](https://github.com/Pukujan/agent-custom-setup/pull/16) |
| Optional jev-gate-pin stub | planned | Open PR (Refs [#17](https://github.com/Pukujan/agent-custom-setup/issues/17)) proposes stub + Fish fixtures | Not merged; not in registry on `main` | [PR #18](https://github.com/Pukujan/agent-custom-setup/pull/18) |

**Boundaries:** no API keys, tokens, cookies, or `.env` contents ever land here; do not force-push shared branches; do not merge your own work unless the owner asks; planned PRs stay labeled planned until merge.

## Try it

Clone and cold-start the way a fresh agent session should:

```bash
git clone https://github.com/Pukujan/agent-custom-setup
cd agent-custom-setup
# read HANDOFF.md → checkpoints/CURRENT.md → active tasks/TASK-*.md
# policy + registry
# POLICY.md  registry.json
```

Install / verify the multi-agent hotload pack (needs pinned helper checkouts — see [`HOTLOAD.md`](modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md)):

```bash
python modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py
python -m pytest modules/coordination/multi-agent-hotload/v0.1.0/tests -q
```

Want the InferHub Claude Code launcher? Copy from `modules/claude-code/inferhub-litellm/v0.2.0/` after reading its module README; put real key values only in a gitignored `.env` outside this repo.

<!-- continuity:task-anchor ACS — product story above; policy in POLICY.md / AGENTS.md -->
