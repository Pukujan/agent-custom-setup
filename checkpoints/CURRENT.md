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

- ACS-0004 (#28) blind recovery-routing replay — issue #28 centers whether low-cost local Laya can surface actionable recovery for consequential intent/research drift. Laya is primary; OpenJev/Kev are optional comparators. Local adapter/profile 1.2.0 changes add next-response acknowledgment, assistant plan/claim boundaries, plan-to-intent checks, and shadow recovery routes. They are not yet tested after the last fixture correction or pushed. No Laya inference/full-corpus run occurred. Parent: none; dependencies: none. Owner correction: [#5894826843](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5894826843).
- ACS-0002 (#5) CI-gate ENFORCEMENT — workflow + markers landed as definition (b094c07); hosted verification blocked by account plan: private-repo Actions runs fail zero-step/zero-billable; private-repo protected branches need Pro/Team/Enterprise (docs.github.com verified 2026-09-26T00:1Z; URLs in task file). Owner options: public / Pro+budget / self-hosted / #9-agent CI/CD converges.

## Queued

- #9/#10 (other agent) policy + multi-setup registry schema + InferHub Claude module v0.2.0 — #10 head 7dee099 base 1c44c8d (+7 behind main), diff disjoint from CURRENT/AGENTS today; owner/#9-agent syncs before merge, then re-verify README registry/status lines against #10's registry.json + modules/.
- #1/#2 scaffold branch refresh (currently CONFLICTING vs rewritten README).
- After #9/#2 merge: re-verify README claims against main reality (status-at-a-glance line, evidence table).

## Blockers

- #5 enforcement as above. Observed counts this session: public sibling project-continuity-modules Actions 387 runs, latest success 22:59Z (2026-09-25).

## Next atomic action

On the other PC, pull `task/ACS-25-dual-jev-gates`, rerun `tests/test_laya_typed_decisions_v1.py`, fix any failures, then verify the exact Laya runtime/checkpoint and resource budget before a bounded synthetic trial. Do not start full transcript inference until the suite passes and the input manifest is validated.
