# TASK-ACS-0008 — Narrow ACS to execution coordination

<!-- continuity:task {"acceptance": ["ACS root tree ships coordination only: JEV gates, jev-omp, jev-benchmark, ops-db, session-ops-capture, docs/knowledge JEV notes, and the claude-code module are removed from main", "registry.json registers exactly one module (multi-agent-hotload @ 0.1.0); PROJECT.md carries the layer-ownership table; POLICY.md states what ACS owns", "root README, .content-system/project-brief.json, and the pack docs describe the coordination product with no JEV/OMP/launcher product framing", "check_pins.py exits OK, the hotloader pack tests pass, and no CI step silently passes over a deleted path", "PCM delivery: checkpoint + PR Refs #44 #52 #63"], "depends_on": [], "goal": "Narrow agent-custom-setup to execution coordination only: move the JEV decision tooling, the oh-my-pi runtime, and the Claude Code setup out to their own repos, and make PROJECT.md, POLICY.md, registry.json, the root README, and the pack docs say exactly that.", "id": "ACS-0008", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/44", "next_action": "Run check_pins.py + the pack tests, commit the narrowing, push the branch, and open the PR (Refs #44 #52 #63).", "owner": "owner/Pukujan (Claude session)", "priority": "P1", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "active", "why": "Owner direction: ACS is the repo agent-management setup that helps multiple agents work together. Decision-making (JEV) is parked, and the JEV court/benchmark tooling, the oh-my-pi runtime, and the Claude Code launcher belong in their own repos. Keeping them here made ACS self-contradictory about what it is."} -->

- Status: active
- Owner / primary writer: owner/Pukujan (Claude session)
- Priority: P1
- Depends on: none
- Leaf owning issue: [#44](https://github.com/Pukujan/agent-custom-setup/issues/44)
- Supersedes direction on: [#52](https://github.com/Pukujan/agent-custom-setup/issues/52) (coordination stays in ACS, not OIO), [#63](https://github.com/Pukujan/agent-custom-setup/issues/63) (parked tenants move out, not parked inside)
- Branch: `task/ACS-narrow-to-coordination`

## Goal

Make ACS mean one thing: **execution coordination** for multi-agent work on one
repository, shipped as the multi-agent hotload pack. Everything that is not that
leaves:

- JEV decision tooling (`jev-oss-compare`, `jev-ambiguity-gate`,
  `jev-research-gate`, `jev-gate-pin`, `jev-shared`, `ops-db`,
  `session-ops-capture`) → `Pukujan/jev-dump`.
- The oh-my-pi runtime (`oh-my-pi/`) and the reader/benchmark evals (`evals/`) →
  `Pukujan/jev-dump`.
- The Claude Code setup (`modules/claude-code/`) → `Pukujan/claude-code-launcher`.
- JEV knowledge notes (`docs/knowledge/jev-*.md`).

And the docs say so: `PROJECT.md` (layer-ownership table), `POLICY.md`,
`registry.json` (one module), the root `README.md`, and the pack docs.

## Why

Owner direction 2026-10-04: ACS is "the repo agents management setup that helps
multiple agents work together." The JEV court/benchmark, the oh-my-pi runtime,
and the Claude Code launcher are separate products. Leaving them inside ACS made
the repo self-contradictory about what it owns and confused both agents and
humans reading it.

## Allowed files

- `.github/workflows/ci.yml` (remove steps that only exercised deleted paths)
- `registry.json`, `PROJECT.md`, `POLICY.md`, `README.md`, `AGENTS.md`
- `.content-system/{asset-manifest,visual-style,project-brief}.json`, `assets/IMAGE_NOTES.md`, `assets/acs-readme-hero-prompt.md`
- `modules/coordination/multi-agent-hotload/v0.1.0/**`
- `checkpoints/CURRENT.md`, `tasks/TASK-ACS-0008-*.md` (this record)
- Deletions of the moved-out trees listed in Goal.

## Non-goals

- No change to the PCM/CGM pins (PCM CLI 0.6.0 @ `4e23854…`; CGM 0.5.12 @
  `6831f91e…`).
- No new coordination runtime code (the pack stays prose + validators; the
  implementation gap stays open on #60).
- No vendoring of PCM, CGM, or the moved-out repos' source.

## Evidence

- The moved-out trees are rebuilt and pushed to `Pukujan/jev-dump` and
  `Pukujan/claude-code-launcher` before removal from ACS.
- `check_pins.py` → `check_pins: OK (15 projections agree with pins.json)`.
- Hotloader pack tests pass.
- No CI step globs a deleted path and exits 0 on zero files.

## Next atomic action

Run `check_pins.py` + the pack tests, commit the narrowing, push the branch, and
open the PR (Refs #44 #52 #63).

## Checkpoint log

### 2026-10-04 — narrow to coordination (as-of; live issues own progression)

Completed:
- Moved JEV decision tooling, the oh-my-pi runtime, the reader/benchmark evals,
  and the Claude Code setup out of ACS to their own repos.
- Rewrote `registry.json` to a single module, filled `PROJECT.md` with the
  layer-ownership table, rewrote `POLICY.md` around what ACS owns.
- Rewrote the root `README.md`, `.content-system/project-brief.json`, the pack
  docs, and the image provenance to the coordination product.
- Removed the two CI steps that only exercised deleted paths (config-template
  parse, TypeScript syntax check) rather than leave silent false-passes.

Evidence:
- `check_pins.py` OK; hotloader pack tests pass.

Decisions:
- Coordination stays in ACS (supersedes #52's move to OIO).
- JEV is parked in `jev-dump`, not kept inside ACS (#44, #63 direction revised).

Blocked/uncertain:
- The pack stays prose + validators; the coordination runtime implementation gap
  stays open on #60 (no executor is added by this task).
- Historical task records (ACS-0001/0002/0003/0006/0007) still describe the
  pre-narrowing tree; they are kept as as-of history, not rewritten.

Next: commit, push, open the PR (Refs #44 #52 #63).

### 2026-10-04 — hero re-render (as-of; live issues own progression)

Completed:
- Re-rendered `assets/acs-readme-hero.png` to the coordination-only story: the
  previous raster's baked-in subtitle still read "installs decision gates"
  (stale JEV framing). New panel subtitle: "The multi-agent hotloader gives your
  coding agents roles, a decision boss, and proposals that become PRs".
- Synced `README.md` alt text, `.content-system/asset-manifest.json`
  (dimensions 1280x720, new SHA-256 `65e43d5b…`, subtitle, prompt recipe,
  review), `assets/acs-readme-hero-prompt.md`, and `assets/IMAGE_NOTES.md`.

Evidence:
- Native output is 1280x720; stored as PNG (lossless re-encode of native pixels,
  no upscaling) to satisfy the adopter PNG-hero contract.
- `check_pins.py` OK; hotloader pack tests pass (21 passed, 2 skipped); CI
  `gates` pass on PR #68 head `9842f81`.

Decisions:
- Swapped at native 1280x720 (owner choice) rather than upscaling to the old
  2816x1584; the asset is stored as PNG because the adopter contract requires a
  PNG hero, and the JPEG->PNG step is lossless.

Blocked/uncertain:
- None for this increment.

Next: await owner go/no-go to merge PR #68.
