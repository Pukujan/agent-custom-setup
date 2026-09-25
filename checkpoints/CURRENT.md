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

- ACS-0002 gate blocked at infrastructure layer (correction supersedes earlier blocker wording): `ci` runs on PR #6 fail ~2–5 s with **zero steps, zero billable ms, no logs** (observed twice: run 36196958507, jobs 108274881569 / rerun 108275962556; `gh api actions/runners` → 0; Actions settings enabled/all). Observed 2026-09-25: public sibling `Pukujan/project-continuity-modules` has 387 runs, latest push run `completed/success` 22:59Z — Actions is healthy account-wide; the block is **private-repo minutes** (this repo is private). GitHub billing docs (fetched via advisor, not yet re-verified at source): Free includes 2,000 Linux min/month **account-wide for private repos**; public repos on standard runners are free/unmetered — so a public conversion clears runner allocation AND private-repo branch-protection plan eligibility at once. Spend-limit/usage check needs `gh auth refresh -h github.com -s user` (current token 404s on billing endpoints). Decision stands: `main` protection + auto-merge deliberately NOT applied while the required check cannot pass (fail closed).

## Next atomic action

Owner: check/restore Actions capacity (github.com/settings/billing — spend limit/usage; or monthly reset; or self-hosted runner; or make repo public — note protection on private repos may itself need a paid plan; observe). Then `gh run rerun 36196958507 --failed` → expect check context **`gates`** (the job id; workflow is named `ci` but no job `name:` was set) green on #6; then apply protection requiring `gates` with `enforce_admins=true` (admins bypassing defeats the gate; `restrict_pushes` availability = observe at apply time) + auto-merge #6; after merge rebase #4, confirm `gates` on it, owner merges.
