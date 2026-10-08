# Current Repository Checkpoint

<!-- continuity:current {"active_task":"ACS-0009","active_task_file":"tasks/TASK-ACS-0009-licensing.md","protocol_version":"0.1.0-draft","schema":"project-continuity.current.v1"} -->

This is an as-of projection; live GitHub issues own progression. Link the owning leaf, parent ancestry and dependencies for active work.

**Page handoff (2026-10-07).** Agents in this repository resume the public-page work from https://github.com/Pukujan/agent-custom-setup/issues/83 (`ACS-0053`, branch `task/ACS-0053-page-handoff-here`). They do not resume from app-builder-automation #58 or from a local folder. The old page content is scrapped. Active task remains `ACS-0009`.

## Program state

Phase: ACS narrowed to **execution coordination only**. The JEV decision tooling, the oh-my-pi runtime, the reader/benchmark evals, and the [CC] setup have moved out to their own repos (`Pukujan/jev-dump`, `Pukujan/claude-code-launcher`). `registry.json` registers exactly one module (`multi-agent-hotload` @ 0.1.0); `PROJECT.md` carries the layer-ownership table; `POLICY.md`, the root `README.md`, and the pack docs describe the coordination product. CI enforcement live (required `gates` + protection). Open gaps are the coordination runtime implementation (#60) and the JEV/dump-side issues now living in their new repos.

## Completed

- continuity protocol initialized.
- ACS-0001 (#3) oh-my-pi module — merged 7df54a1; #3 closed with verified closeout (owner-directed merge; hosted gates unverified, recorded).
- ACS-0003 (#7) story-first README + CGM 0.4.0 adapter + omp reader-eval harness (suite PASS, holdout not_run) — merged f0d84fb; #7 closed with verified closeout.
- ACS-0006 (leaf #19) pin sync + regenerated README visuals — PR #45 merged `main` @ `5bb85de`, `gates` SUCCESS (run 36805930988). Adapter + projections pinned CGM 0.5.7 @ `c069613` (eight modules) and PCM CLI 0.6.0 @ `4e23854` (ci.yml `PCM_PIN` bumped from 0.5.0-era `743d50e`); root README regenerated product-only; #19 closed. Receipts on #19/#44/#46/#11. Related merged PRs: #16→`3253b39` (#15 closed), #18→`57f6888` (#17 closed), #20→`6b02503`, #23→`e5c5cc3` (#22 reopened — module landed but the live ≥30-interaction Langfuse/SQLite receipt is unmet; stays open).
- ACS-0006 follow-up (leaf #19) README raster refresh — PR #48 merged `main` @ `41ad617`, `gates` SUCCESS (run 36807670725): both README rasters re-rendered with the owner's new image model (`xai-oauth/grok-imagine-image`), manifest hashes + prompt records updated, validator helper+adapter VALID on the merged tree. Merge facts for #45/#47/#48: `gates` passed on each merged head; the required 1-approving-review gate was bypassed by the owner's `--admin` token (author self-approval is blocked) — recorded on #19 and each PR.
- ACS-0007 (#55, parent #52) CGM 0.5.12 pin move — the release train re-certified CGM at 0.5.12 @ `6831f91e…`, so the pack's hard pin moved in place (module stays `v0.1.0`): `pins.json` `cgm.version` 0.5.12 with `0.5.7`/`c069613` under `superseded`, all 15 declared projections agree (`check_pins.py` OK), `PROMPT_INJECT.md` regenerated from 0.5.12's `docs/writing-routing.json`, four live surfaces outside the checker's scan moved. Task record `tasks/TASK-ACS-0007-cgm0512-pin.md`.

## Active

- ACS-0014 (#71) dev root hygiene — `HOTLOAD.md` / `BEHAVIOR.md` / `PROMPT_INJECT.md` state that the dev root holds one main checkout per repo; new `scripts/dev_root_check.py` flags everything else and can move it into the ACS cache; `hotload_check` warns on findings and refuses dependency checkouts inside the dev root. Task record `tasks/TASK-ACS-0014-dev-root-hygiene.md`; branch `task/ACS-dev-root-hygiene`.
- ACS-0009 (#69) license the stack — stamp ACS with FSL-1.1-ALv2 (`LICENSE`, `NOTICE`, `TRADEMARK.md`, README section) so a third party may use it freely but not compete; stamp the pinned module repos (PCM, CGM, OIO, agent-stack-train) with Apache-2.0; make `jev-dump` private. Cross-repo observation OIO #24. Task record `tasks/TASK-ACS-0009-licensing.md`; branch `task/ACS-licensing`.
- ACS-0008 (#44, supersedes direction on #52/#63) narrow to coordination — moved the JEV decision tooling (`jev-oss-compare`, `jev-ambiguity-gate`, `jev-research-gate`, `jev-gate-pin`, `jev-shared`, `ops-db`, `session-ops-capture`) and the oh-my-pi runtime + evals out to `Pukujan/jev-dump`; moved the [CC] setup out to `Pukujan/claude-code-launcher`. Rewrote `registry.json` to a single module, filled `PROJECT.md` with the layer-ownership table, rewrote `POLICY.md` and the root `README.md`, `.content-system/project-brief.json`, the pack docs, and the image provenance to the coordination product. Removed the two CI steps that only exercised deleted paths (config-template parse, TypeScript syntax check) rather than leave silent false-passes. Merged `main` @ `e1d7732` (PR #68). Task record `tasks/TASK-ACS-0008-narrow-to-coordination.md`; branch `task/ACS-narrow-to-coordination`. Evidence: `check_pins.py` OK (15 projections agree), hotloader pack tests pass.
- ACS-0002 (#5) CI-gate ENFORCEMENT — workflow + markers on main (b094c07); **hosted verification UNBLOCKED 2026-09-29** (repo now public): branch protection LIVE via `gh api PUT .../protection` 200 — required check `gates` (strict) + 1 approving review + stale-dismiss; Actions succeeds (PR #38 `gates pass` 19s, run 36640336687); auto-merge ENABLED on #38 (SQUASH; state BLOCKED solely pending the owner's approving review). Superseded 2026-09-26 zero-step/403 plan-gap observations preserved on #5 (comment 5900442805), not rewritten.

## Queued

- #9/#10 (other agent) policy + multi-setup registry schema — owner/#9-agent syncs before merge, then re-verify README registry/status lines against #10's `registry.json` + `modules/`.
- After #9/#2 merge: re-verify README claims against main reality (status-at-a-glance line, evidence table).
- Layer-ownership table rollout to the sibling repos (PCM, CGM, OIO) as small separate PRs.

## Blockers

- #5 enforcement as above. Observed counts this session: public sibling project-continuity-modules Actions 387 runs, latest success 22:59Z (2026-09-25).

## Next atomic action

ACS-0009: commit the license files + README section on `task/ACS-licensing`, push the branch, open the PR (Refs #69), and confirm `gates`. Cross-repo: stamp the module repos with Apache-2.0 and make `jev-dump` private.
Owner plan decision on #5 (Actions capacity/protection) remains the open enforcement gate.
