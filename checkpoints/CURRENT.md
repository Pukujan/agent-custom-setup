# Current Repository Checkpoint

<!-- continuity:current {"active_task":"ACS-0002","active_task_file":"tasks/TASK-ACS-0002-ci-gates.md","protocol_version":"0.1.0-draft","schema":"project-continuity.current.v1"} -->

This is an as-of projection; live GitHub issues own progression. Link the owning leaf, parent ancestry and dependencies for active work.

## Program state

Phase: bootstrap; delivery discipline (CI gates) in flight.

## Completed

- continuity protocol initialized.

## Active

- ACS-0002 (#5) CI gates — branch task/ACS-0002-ci-gates: ci.yml + branch protection + auto-merge + PCM issue-log-format marker sync. Refs #3 (clears its no-CI blocker).
- ACS-0001 (#3) oh-my-pi module — PR #4 open at head c3f7f91, pushed, owner-review pending; delivery blocked on ACS-0002 required-check gate (then rebase #4 onto gated main so ci runs on its head).

## Queued

- After ACS-0002 merges: rebase ACS-0001, confirm ci on #4, owner merges; then pick next bounded task.

## Blockers

- ACS-0002 gate is machine-failing at the infrastructure layer: every `ci` run fails in ~2–5s with **zero steps and no logs** (observed twice: run 36196958507, job 108274881569 and rerun job 108275962556; `timing.billable.total_ms: 0`; `gh api actions/runners` → 0; Actions settings enabled/all). Repo is private; Actions minutes/plan not readable with current gh scopes (billing endpoint needs `user` scope). *Inferred:* no GitHub-hosted runner was ever allocated (minutes/eligibility), not a workflow-content error — the job never started. Consequence: `main` protection + auto-merge are deliberately NOT applied yet; a required check that cannot pass would freeze every merge (fail closed). Owner decision needed: add a payment method / check Actions spend limit at github.com/settings/billing, or wait for the Actions reset, or run a self-hosted runner, or make the repo public (2000 free Linux min/mo).

## Next atomic action

Commit the ACS-0002 product (ci.yml, marker sync, task projection, CURRENT), run `continuity checkpoint ACS-0002`, publish the #5 receipt, open the PR, enable auto-merge, then apply `main` protection once `ci` first reports.
