# Current Repository Checkpoint

<!-- continuity:current {"active_task":"ACS-0004","active_task_file":"tasks/TASK-ACS-0004-blind-local-replay.md","protocol_version":"0.1.0-draft","schema":"project-continuity.current.v1"} -->

This is an as-of projection; live GitHub issues own progression. Link the owning leaf, parent ancestry and dependencies for active work.

## Program state

Phase: registry + module + docs live on main; CI enforcement remains the open gap.

## Completed

- continuity protocol initialized.
- ACS-0001 (#3) oh-my-pi module — merged 7df54a1; #3 closed with verified closeout (owner-directed merge; hosted gates unverified, recorded).
- ACS-0003 (#7) story-first README + CGM 0.4.0 adapter + omp reader-eval harness (suite PASS, holdout not_run) — merged f0d84fb; #7 closed with verified closeout.

## Active

- ACS-0004 (#28) blind recovery-routing replay — issue #28 centers whether low-cost local Laya can surface actionable recovery for consequential intent/research drift. Laya is primary; OpenJev/Kev are optional comparators. Merged on main via PR #26/#30/#31/#32/#33 (heads `69a34dd`, `0e8f302`, `bc78910`, `9699c397`, `e6d5af96`; gates green on each): adapter/profile 1.2.0, pool/chmod fixes, 13/13 adapter suite, M01–M14 protocol restore + 24-case M01–M28 metamorphic + seeded-fuzz suite (mutation-proven, crib-scan clean; receipts `laya-local-20260929T184900Z.json`, `laya-metamorphic-20260929.json`), pinned-model cold smoke, and the bounded local resource attempt (`laya-resource-trial-20260929.json`; non-extrapolable). Synthetic mechanics only — report's M01–M14 stays Unverified, holdout not implemented, suites not CI-enforced. A capped-harvest LOCAL PILOT ran the frozen DAG (owner direction 2026-09-29): 805/805 jobs, 7/80 streams, receipt `laya-pilot-20260929.json`; escalates = model uncertainty on truncated tool text; ack rows = export artifacts; non-evidence. No full-corpus replay has run: the verified 81-file corpus lives on hosts unreachable from this device (Gravebuster SSH denied; Cortex SSH closed). Parent: none; dependencies: none. Owner correction: [#5894826843](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5894826843).
- ACS-0002 (#5) CI-gate ENFORCEMENT — workflow + markers landed as definition (b094c07); hosted verification blocked by account plan: private-repo Actions runs fail zero-step/zero-billable; private-repo protected branches need Pro/Team/Enterprise (docs.github.com verified 2026-09-26T00:1Z; URLs in task file). Owner options: public / Pro+budget / self-hosted / #9-agent CI/CD converges.
- ACS-0005 (#37, parent #35) OMP loop hardening — jev-court v2 (fail-quiet, budgets, no-wake, stop-aware, durable decisions), new loop-guard, silence-first roster + scope advisor disabled, config storm keys (`syncBacklog` enum-type fix, `goal.continuationModes: []`, `todo.remindersMax: 1`); owner's live `~/.omp/agent/` cut over with dated backup. Verified: 32/32 assertions replaying the real #35 fixture (v1's 83 injected messages → 0), `omp -p` clean load on installed v18.4.4. Awaiting PR + merge.

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
