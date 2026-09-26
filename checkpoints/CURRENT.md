# Current Repository Checkpoint

<!-- continuity:current {"active_task":"ACS-0003","active_task_file":"tasks/TASK-ACS-0003-readme-docs.md","protocol_version":"0.1.0-draft","schema":"project-continuity.current.v1"} -->

This is an as-of projection; live GitHub issues own progression. Link the owning leaf, parent ancestry and dependencies for active work.

## Program state

Phase: bootstrap; docs delivery in flight while CI-gate work unblocks.

## Completed

- continuity protocol initialized.

## Active

- ACS-0003 (#7) README + CGM adapter — PR #8 head e8dccaa; product complete (validator VALID), reader-eval suite v3 PASS (M-01/M-04/M-09 + stub differential; HOLDOUT not_run disclosed), pending owner review/merge.
- ACS-0001 (#3) oh-my-pi module — PR #4 head c3f7f91 pushed, owner review pending.
- ACS-0002 (#5) CI gates — PR #6 head 943d4d4; blocked: private-repo runner allocation + private protection plan-gated per verified docs (see Blockers; owner options recorded on #5).

## Queued

- After #6 merges (gated main): sync #4 by merging main into it (append-only; no rebase/force-push), confirm `gates`, owner merges; same sync pattern for #8/#2 if protection lands first.

## Blockers

- Two verified layers, per primary-source docs 2026-09-26T00:1Z: (1) private-repo Actions usage blocked at account level (zero-step/zero-billable runs; public sibling healthy → private-specific); (2) **private-repo protected branches require Pro/Team/Enterprise — Free lists them as Pro "advanced private-repo tool"** (githubs-plans; about-protected-branches itself has no plan text; earlier attribution corrected). Account plan UNOBSERVED (gh api user .plan.name empty). Owner options: make repo public (fixes both), Pro/budget, or record gate plan-blocked and merge under fail-closed exception with issues kept OPEN and NOT marked delivered (PCM: owner direction cannot waive required gates — only a policy amendment supersedes). Protection/auto-merge unapplied meanwhile.

## Next atomic action

Publish #7 eval-completion receipt; owner decision: merge #8 as-is now (validator+eval gates pass locally-recorded), or wait for Actions plan decision (#6/#5) so #8 lands on a gated main.
