# Current Repository Checkpoint

<!-- continuity:current {"active_task":"ACS-0002","active_task_file":"tasks/TASK-ACS-0002-ci-gates.md","protocol_version":"0.1.0-draft","schema":"project-continuity.current.v1"} -->

This is an as-of projection; live GitHub issues own progression. Link the owning leaf, parent ancestry and dependencies for active work.

## Program state

Phase: registry + module + docs live on main; CI enforcement remains the open gap.

## Completed

- continuity protocol initialized.
- ACS-0001 (#3) oh-my-pi module — merged 7df54a1; #3 closed with verified closeout (owner-directed merge; hosted gates unverified, recorded).
- ACS-0003 (#7) story-first README + CGM 0.4.0 adapter + omp reader-eval harness (suite PASS, holdout not_run) — merged f0d84fb; #7 closed with verified closeout.

## Active

- ACS-0002 (#5) CI-gate ENFORCEMENT — workflow + markers landed as definition (b094c07); hosted verification blocked by account plan: private-repo Actions runs fail zero-step/zero-billable; private-repo protected branches need Pro/Team/Enterprise (docs.github.com verified 2026-09-26T00:1Z; URLs in task file). Owner options: public / Pro+budget / self-hosted / #9-agent CI/CD converges.

## Queued

- #9/#10 (other agent) policy + multi-setup registry schema + InferHub Claude module v0.2.0 — #10 head 7dee099 base 1c44c8d (+7 behind main), diff disjoint from CURRENT/AGENTS today; owner/#9-agent syncs before merge, then re-verify README registry/status lines against #10's registry.json + modules/.
- #1/#2 scaffold branch refresh (currently CONFLICTING vs rewritten README).
- After #9/#2 merge: re-verify README claims against main reality (status-at-a-glance line, evidence table).

## Blockers

- #5 enforcement as above. Observed counts this session: public sibling project-continuity-modules Actions 387 runs, latest success 22:59Z (2026-09-25).

## Next atomic action

Owner plan decision on #5 (Actions capacity/protection) — the only open enforcement gate; suite-5 (hardened cohort) landing under evals/results/suite5/ when done.
