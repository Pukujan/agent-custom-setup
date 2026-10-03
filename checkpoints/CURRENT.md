# Current Repository Checkpoint

<!-- continuity:current {"active_task":"ACS-0004","active_task_file":"tasks/TASK-ACS-0004-blind-local-replay.md","protocol_version":"0.1.0-draft","schema":"project-continuity.current.v1"} -->

This is an as-of projection; live GitHub issues own progression. Link the owning leaf, parent ancestry and dependencies for active work.

## Program state

Phase: registry + modules + hotloader-first docs on main; CI enforcement live (required `gates` + protection); open gaps are the physical module split (#44), pin-manifest automation (#46), the live session-ops receipt (#22), and the blind replay (#28).

## Completed

- continuity protocol initialized.
- ACS-0001 (#3) oh-my-pi module — merged 7df54a1; #3 closed with verified closeout (owner-directed merge; hosted gates unverified, recorded).
- ACS-0003 (#7) story-first README + CGM 0.4.0 adapter + omp reader-eval harness (suite PASS, holdout not_run) — merged f0d84fb; #7 closed with verified closeout.
- ACS-0006 (leaf #19) pin sync + regenerated README visuals — PR #45 merged `main` @ `5bb85de`, `gates` SUCCESS (run 36805930988). Adapter + projections now pin CGM 0.5.7 @ `c069613` (eight modules) and PCM CLI 0.6.0 @ `4e23854` (ci.yml `PCM_PIN` bumped from 0.5.0-era `743d50e`); root README regenerated product-only with the multi-agent hotloader as the primary feature and two narrative rasters (`assets/acs-readme-hero.png`, hub-and-spoke `assets/acs-three-modules.png`) with full manifest provenance; validator helper+adapter VALID + writing OK recorded on #19; #19 closed. Receipts on #19/#44/#46/#11. Related merged PRs: #16→`3253b39` (#15 closed), #18→`57f6888` (#17 closed), #20→`6b02503`, #23→`e5c5cc3` (#22 reopened — module landed but the live ≥30-interaction Langfuse/SQLite receipt is unmet; stays open).
- ACS-0006 follow-up (leaf #19) README raster refresh — PR #48 merged `main` @ `41ad617`, `gates` SUCCESS (run 36807670725): both README rasters re-rendered with the owner's new image model (`xai-oauth/grok-imagine-image`), manifest hashes + prompt records updated, validator helper+adapter VALID on the merged tree. Merge facts for #45/#47/#48: `gates` passed on each merged head; the required 1-approving-review gate was bypassed by the owner's `--admin` token (author self-approval is blocked) — recorded on #19 and each PR.

## Active

- ACS-0004 (#28) blind recovery-routing replay — issue #28 centers whether low-cost local Laya can surface actionable recovery for consequential intent/research drift. Laya is primary; OpenJev/Kev are optional comparators. Merged on main via PR #26/#30/#31/#32/#33 (heads `69a34dd`, `0e8f302`, `bc78910`, `9699c397`, `e6d5af96`; gates green on each): adapter/profile 1.2.0, pool/chmod fixes, 13/13 adapter suite, M01–M14 protocol restore + 24-case M01–M28 metamorphic + seeded-fuzz suite (mutation-proven, crib-scan clean; receipts `laya-local-20260929T184900Z.json`, `laya-metamorphic-20260929.json`), pinned-model cold smoke, and the bounded local resource attempt (`laya-resource-trial-20260929.json`; non-extrapolable). Synthetic mechanics only — report's M01–M14 stays Unverified, holdout not implemented, suites not CI-enforced. A capped-harvest LOCAL PILOT ran the frozen DAG (owner direction 2026-09-29): 805/805 jobs, 7/80 streams, receipt `laya-pilot-20260929.json`; escalates = model uncertainty on truncated tool text; ack rows = export artifacts; non-evidence. No full-corpus replay has run: the verified 81-file corpus lives on hosts unreachable from this device (Gravebuster SSH denied; Cortex SSH closed). Parent: none; dependencies: none. Owner correction: [#5894826843](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5894826843).
- ACS-0002 (#5) CI-gate ENFORCEMENT — workflow + markers on main (b094c07); **hosted verification UNBLOCKED 2026-09-29** (repo now public): branch protection LIVE via `gh api PUT .../protection` 200 — required check `gates` (strict) + 1 approving review + stale-dismiss; Actions succeeds (PR #38 `gates pass` 19s, run 36640336687); auto-merge ENABLED on #38 (SQUASH; state BLOCKED solely pending the owner's approving review). Superseded 2026-09-26 zero-step/403 plan-gap observations preserved on #5 (comment 5900442805), not rewritten.
- ACS-0007 (#55, parent #52) CGM 0.5.12 pin move — the release train re-certified CGM at 0.5.12 @ `6831f91e…`, so the pack's hard pin moves in place (module stays `v0.1.0`, matching `895ae43`): `pins.json` `cgm.version` 0.5.12 with `0.5.7`/`c069613` under `superseded`, all 15 declared projections agree (`check_pins.py` OK), `PROMPT_INJECT.md` regenerated from 0.5.12's `docs/writing-routing.json`, four live surfaces outside the checker's scan moved (`asset-manifest.json`, `brand-language.json`, `project-brief.json`, root `README.md`). Branch `task/ACS-0052-cgm-0512-pin` (worktree `.worktrees/ACS-0052-cgm-0512-pin`); pack tests 23 passed; validator helper+adapter VALID. Task record `tasks/TASK-ACS-0007-cgm0512-pin.md`.
- ACS-0008 (#64, parent #9) macOS launcher: there is no Mac way to run Claude Code through InferHub with one click. New module `modules/claude-code/inferhub-litellm-macos/v0.1.0/` adds a single double-click `Launch Claude InferHub.command` that bootstraps itself and routes like Windows (it runs the litellm-ckff-ops seat scripts unchanged). Verified on Linux only (shellcheck, bash 3.2.57/5 `-n`, `tests/dry_run.sh` PASS); a Mac run is pending. Branch `task/ACS-0008-macos-launcher`. Task record `tasks/TASK-ACS-0008-macos-launcher.md`.

## Queued

- #9/#10 (other agent) policy + multi-setup registry schema + InferHub Claude module v0.2.0 — #10 head 7dee099 base 1c44c8d (+7 behind main), diff disjoint from CURRENT/AGENTS today; owner/#9-agent syncs before merge, then re-verify README registry/status lines against #10's registry.json + modules/.
- #1/#2 scaffold branch refresh (currently CONFLICTING vs rewritten README).
- After #9/#2 merge: re-verify README claims against main reality (status-at-a-glance line, evidence table).

## Blockers

- #5 enforcement as above. Observed counts this session: public sibling project-continuity-modules Actions 387 runs, latest success 22:59Z (2026-09-25).

## Next atomic action

ACS-0005: owner review + merge PR (Refs #35 #37); then live-session confirmation (court disabled at start, no post-settle advisory wakes) and receipt on #37.
ACS-0004 next: on a corpus host (requires Gravebuster key or Cortex SSH access), run `python modules/coordination/jev-oss-compare/v0.1.0/scripts/laya_typed_decisions/v1/runner.py run --source <dir-of-81-jsonl> --model-dir <pinned-snapshot> --output <private-dir-outside-repo> --run-id <id> --execute-local` from `task/ACS-0004-laya-benchmark`, then refresh the HTML report from terminal receipts.
Owner plan decision on #5 (Actions capacity/protection) remains the open enforcement gate.
