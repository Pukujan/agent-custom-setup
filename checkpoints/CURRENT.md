# Current Repository Checkpoint

<!-- continuity:current {"active_task":"ACS-0003","active_task_file":"tasks/TASK-ACS-0003-readme-docs.md","protocol_version":"0.1.0-draft","schema":"project-continuity.current.v1"} -->

This is an as-of projection; live GitHub issues own progression. Link the owning leaf, parent ancestry and dependencies for active work.

## Program state

Phase: bootstrap; docs delivery in flight while CI-gate work unblocks.

## Completed

- continuity protocol initialized.

## Active

- ACS-0003 (#7) README + CGM 0.4.0 adapter — branch task/ACS-0003-readme-docs (this projection); story-first README + `.content-system/` targeting pinned-helper validator VALID.
- ACS-0001 (#3) oh-my-pi module — PR #4 head c3f7f91 pushed, owner review pending.
- ACS-0002 (#5) CI gates — PR #6 head 7488996; blocked on Actions runner capacity (see Blockers).

## Queued

- After #6 merges (gated main): rebase #4, confirm ci, owner merges; refresh PR #2 branch so ci covers it.

## Blockers

- GitHub Actions cannot allocate a hosted runner for private-repo jobs on this account (observed on PR #6: zero-step ~2s failures, billable 0 ms, twice). Owner action: payment method/spend limit at github.com/settings/billing, monthly reset, self-hosted runner, or public repo. main protection + auto-merge deliberately deferred until ci can pass.

## Next atomic action

Author ACS-0003 deliverable, iterate pinned CGM validator to VALID, commit product, run `continuity checkpoint ACS-0003`, publish #7 receipt, open PR with Refs #7.
