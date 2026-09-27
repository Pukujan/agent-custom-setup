# Agent Custom Setup

![Registry icon](assets/registry-icon.svg)

> **Durable, reviewable agent setups — so a fresh session can resume without living in one chat's memory.**

## Why this exists

An agent setup is usually invisible work: a judge model wired into an advisor loop, a roster of critic roles, a launch script, a `.env` full of keys. It lives in whatever session built it. When that session ends, the next reader — human or agent — inherits nothing they can trust. **Setup knowledge evaporates with the session.**

The concrete situation this repo exists for: an advisor/JEV judge configuration that had been tuned inside a single chat session. The judge role pointed at a model selector that 401'd on every candidate, so the judge had never actually contributed a decision — and nobody outside that session could see any of it. This repository turned that invisible state into a versioned module with an evidence trail, which is exactly what PCM (Project Continuity Protocol) and this repo's task issues are for.

## What this project is

**agent-custom-setup** is a private, PCM-governed home for customized agent setups. It is for operators who keep agent configuration on a personal machine, for fresh agent sessions that must resume project state from the repository alone, and for future module authors adding other stacks.

It is **not** a secrets vault (keys never enter git), not a hosted agent platform, and not a guarantee that any setup works on your machine unchanged.

**Status at a glance:** on `main` today, the only merged increment is the PCM continuity protocol itself; the oh-my-pi module (advisor/JEV config + `jev-court` extension) is delivered but still pending owner review on pull request #4; the registry/Claude Code scaffold (pull request #2) and multi-module adoption are planned. Every module claim below is tied to that reality, with the citations in the Evidence table.

Two contracts shape every file here: PCM makes GitHub issues authoritative for task state, with checked-in `PROJECT.md` / `checkpoints/CURRENT.md` / `tasks/*` as versioned projections; CGM (Content Generation Modules) binds every promise in human-facing docs to pinned evidence — the writing method behind this README, including its scanability rules, comes from the CGM [playbook](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/README_PLAYBOOK.md).

## What you can make or use

- **The oh-my-pi module (product of issue #3):** advisor/JEV config templates (`config.yml`, `models.yml`, `WATCHDOG.yml`) and the `jev-court.ts` extension that adjudicates every advisor note through the JEV judge with risk-tiered thresholds — currently delivered on task branch `task/ACS-0001-oh-my-pi-module` behind open [pull request #4](https://github.com/Pukujan/agent-custom-setup/pull/4). Details: [oh-my-pi README @ 0b29fdc](https://github.com/Pukujan/agent-custom-setup/blob/0b29fdccda48c875fac07b7f087b59609cbbfb99/oh-my-pi/README.md).
- **A resumable continuity record:** the PCM adoption is merged on `main` — [checkpoints/CURRENT.md @ 1c44c8d](https://github.com/Pukujan/agent-custom-setup/blob/1c44c8d2f25cb71e8acb20253e2cc26cd682af81/checkpoints/CURRENT.md) shows how any fresh session cold-starts (read order in `HANDOFF.md`).
- **A planned registry of further modules:** a sanitized Claude Code launcher scaffold with `registry.json` temporal metadata exists on `feat/scaffold-pcm-cgm-1` behind open [pull request #2](https://github.com/Pukujan/agent-custom-setup/pull/2); its shape is described in [issue #1](https://github.com/Pukujan/agent-custom-setup/issues/1) and [`module.json` @ 8420b78](https://github.com/Pukujan/agent-custom-setup/blob/8420b7876a77b38985b652541071e8cca72288ca/modules/claude-code/module.json). Pending PRs are pending: nothing here claims they are merged.
- **A no-secrets template pattern:** every provider key is referenced by environment-variable *name* only; real values live in gitignored `.env` files outside this repository.

## How it works

The loop is small and repeatable, and you can walk it without writing code:

1. A task begins as a **GitHub issue** — issues own scope, acceptance, and lifecycle; `AGENTS.md` states the contract.
2. Work happens on a task branch; each increment ends with a `continuity checkpoint` (stable request ID, commit, push) and a **receipt comment on the issue** keyed to the exact SHA.
3. A **PR + review (and, once CI capacity lands, required checks)** merges into `main`; only then may a task claim "delivered."
4. Setups that merge are **copied into `~/.omp/agent/`** (or equivalent) from module templates that carry env-var names, never values.
5. Docs like this README are written against the **pinned CGM adapter** in `.content-system/`, and validated with the helper's own deterministic script.

**Worked example (real, not hypothetical):** issue #3 traced the judge's silent 401s, re-pointed the role to a working OpenRouter decisions provider, and verified live: three real advisor notes were adjudicated `act` at confidence 0.92 / 0.94 / 0.96, and a synthetic trivia note was correctly `ignore`d at 0.98 — evidence recorded on [issue #3](https://github.com/Pukujan/agent-custom-setup/issues/3). What had been one chat's invisible debugging session became a reviewable module increment.

## Evidence and boundaries

Claim fields follow the CGM `content-generation.claim-evidence.v2` contract (claim, source, status, supports, limits, source_revision, recorded_at); the full machine-readable set is in [`.content-system/project-brief.json`](.content-system/project-brief.json). A valid citation establishes traceability, not truth.

| Claim | Status | Supports | Limits | Source |
|---|---|---|---|---|
| PCM adopted; issues own progression; projections versioned | shipped | `CURRENT.md`/`PROJECT.md` on default branch | scaffold discipline, not proof every future task follows it | [CURRENT.md @ 1c44c8d](https://github.com/Pukujan/agent-custom-setup/blob/1c44c8d2f25cb71e8acb20253e2cc26cd682af81/checkpoints/CURRENT.md) |
| oh-my-pi module with JEV wiring + jev-court extension | shipped (on task branch, PR #4 open) | module files exist with install steps and verified behavior | **not merged to default branch yet** | [oh-my-pi README @ 0b29fdc](https://github.com/Pukujan/agent-custom-setup/blob/0b29fdccda48c875fac07b7f087b59609cbbfb99/oh-my-pi/README.md) |
| Live JEV adjudication after 401 root-cause fix | shipped | 3 notes act@0.92/0.94/0.96; trivia ignore@0.98 (~$0.00005/call) | small sample, one provider, one date (2026-09-25) | [issue #3](https://github.com/Pukujan/agent-custom-setup/issues/3) |
| Registry + sanitized Claude Code launcher module | planned | module scaffold with `secrets_policy` exists | unmerged PR #2; adoption unproven | [module.json @ 8420b78](https://github.com/Pukujan/agent-custom-setup/blob/8420b7876a77b38985b652541071e8cca72288ca/modules/claude-code/module.json) |
| Product boundary: own project state only | planned | scope decision recorded on the tracker | an issue's prose, not measured behavior | [issue #1](https://github.com/Pukujan/agent-custom-setup/issues/1) |

**Boundaries:** no API keys, tokens, cookies, or `.env` contents ever land here; PR-pending work is labeled pending; no hosted platform is claimed; narrative marketing images are not generated yet (see next section); required-CI enforcement is in flight on [issue #5](https://github.com/Pukujan/agent-custom-setup/issues/5), and until it lands, merge discipline is the owner's review.

## Image generation and use

This README is deliberately **text-first**. The visual contract in [`.content-system/visual-style.json`](.content-system/visual-style.json) declares `generation_workflow: "built-in image_gen"`, but [`.content-system/asset-manifest.json`](.content-system/asset-manifest.json) intentionally carries **zero narrative rasters**: no image generator is available on this machine, and pretending hero images exist would violate the same evidence rule as every other claim here. The one shipped asset is the non-narrative [`assets/registry-icon.svg`](assets/registry-icon.svg) (64×64 brand mark, no embedded text). When generation becomes available, hero/problem assets must record prompt, dimensions, SHA-256, alt text, and review decision in the manifest before being linked — procedure in [`assets/IMAGE_NOTES.md`](assets/IMAGE_NOTES.md).

Helper guides for that future step, pinned to the version this adapter declares:
[docs/IMAGE_GUIDE.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/IMAGE_GUIDE.md) ·
[docs/BRAND_DIRECTION.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/BRAND_DIRECTION.md) ·
[docs/CONTENT_RESEARCH.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/CONTENT_RESEARCH.md)

## Templates and guides

Start with what this repository owns:

- Cold-start read order: [`HANDOFF.md`](HANDOFF.md) → [`checkpoints/CURRENT.md`](checkpoints/CURRENT.md) → the active `tasks/TASK-*.md`
- Task/issue templates: [`.github/ISSUE_TEMPLATE/task.md`](.github/ISSUE_TEMPLATE/task.md), [`.github/pull_request_template.md`](.github/pull_request_template.md)
- Continuity schemas: `schemas/v1/*.schema.json` (task, checkpoint, current, recovery, context-pack)
- CGM adapter (what this README was validated against): `.content-system/` pinned to helper **0.4.0** at commit `f85e88bc00362c53061d95ac7811bd9c6ada8e32`

Helper-side sources this output is built from, each pinned at the same commit (literal paths below for validator traceability):
`docs/CONTENT_RESEARCH.md`, `docs/BRAND_DIRECTION.md`, `docs/README_PLAYBOOK.md`, `docs/IMAGE_GUIDE.md`, `docs/PRIOR_WORK.md`, `docs/HOLDOUT_EVALUATION.md`, `docs/MIGRATING_TO_0.2.md`, `docs/MIGRATING_TO_0.3.md`, `docs/MIGRATING_TO_0.4.md`, `docs/README_QUALITY_PDD.md`, `docs/README_QUALITY_SDD.md`, `docs/README_QUALITY_TDD.md`, `docs/PROVENANCE_AND_CITATION.md`, `docs/REVERSE_ANALYSIS_PCM_AND_ADOPTERS.md`, `templates/README.template.md` — all under
[github.com/Pukujan/content-generation-modules/tree/f85e88bc00362c53061d95ac7811bd9c6ada8e32](https://github.com/Pukujan/content-generation-modules/tree/f85e88bc00362c53061d95ac7811bd9c6ada8e32).

## Prior work and references

- **CGM helper** `Pukujan/content-generation-modules` @ 0.4.0 (`f85e88b`) — the README contract this page satisfies; its research lineage is [docs/PRIOR_WORK.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/PRIOR_WORK.md), its citation discipline [docs/PROVENANCE_AND_CITATION.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/PROVENANCE_AND_CITATION.md), and the adopter analysis that shaped this adapter [docs/REVERSE_ANALYSIS_PCM_AND_ADOPTERS.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/REVERSE_ANALYSIS_PCM_AND_ADOPTERS.md).
- **Earlier draft of this README** on `feat/scaffold-pcm-cgm-1` (open PR #2) — reviewed structure reused; claims re-pinned to today's branch/PR reality and Windows-local paths removed.
- **Quality bar** this page was checked against: [README_QUALITY_PDD](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/README_QUALITY_PDD.md) / [SDD](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/README_QUALITY_SDD.md) / [TDD](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/README_QUALITY_TDD.md), holdout method in [docs/HOLDOUT_EVALUATION.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/HOLDOUT_EVALUATION.md), story template in [templates/README.template.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/templates/README.template.md), migration history in [docs/MIGRATING_TO_0.2.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/MIGRATING_TO_0.2.md) / [docs/MIGRATING_TO_0.3.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/MIGRATING_TO_0.3.md) / [docs/MIGRATING_TO_0.4.md](https://github.com/Pukujan/content-generation-modules/blob/f85e88bc00362c53061d95ac7811bd9c6ada8e32/docs/MIGRATING_TO_0.4.md).
- **PCM** governance: `AGENTS.md` here; upstream project `Pukujan/project-continuity-modules`.

## Try it

Clone and cold-start the way a fresh agent session should:

```bash
git clone https://github.com/Pukujan/agent-custom-setup
cd agent-custom-setup
# read HANDOFF.md, then checkpoints/CURRENT.md, then the active tasks/TASK-*.md
gh issue list --repo Pukujan/agent-custom-setup --state open
```

Want the oh-my-pi setup today? Wait for PR #4 to merge (or review it), copy `oh-my-pi/config/*` and `oh-my-pi/extensions/jev-court.ts` into `~/.omp/agent/`, and put real key values only in `~/.omp/agent/.env` — see [oh-my-pi README @ 0b29fdc](https://github.com/Pukujan/agent-custom-setup/blob/0b29fdccda48c875fac07b7f087b59609cbbfb99/oh-my-pi/README.md).

Re-check this page's contract (needs a checkout of the pinned helper):

```bash
python3 <cgm-checkout>/scripts/validate_content_system.py \
  --root <cgm-checkout> --adapter .content-system --project-root .
```

<!-- continuity:task-anchor ACS-0003 — human story above; policy blocks live in AGENTS.md/HANDOFF.md, not here -->
