# TASK-ACS-0002 — Ci Gates

<!-- continuity:task {"acceptance":["gh pr checks on this PR head shows ci passing","gh api repos/Pukujan/agent-custom-setup/branches/main/protection reports required_status_checks context ci and restrict_pushes true; direct push to main is rejected","this PR merges via GitHub auto-merge after ci turns green; merge SHA recorded on issue #5","gh pr checks 4 shows ci green after ACS-0001 head is rebased onto the new main","continuity validate (pinned 0.5.0) exits VALID with zero issue-log-format marker warnings"],"depends_on":[],"goal":"Required ci status check on PRs to main, branch protection, auto-merge enabled; PCM issue-log-format marker sync","id":"ACS-0002","issue_url":"https://github.com/Pukujan/agent-custom-setup/issues/5","next_action":"implement ci.yml + marker sync, commit product, continuity checkpoint ACS-0002, PR, auto-merge, protection","owner":"owner/Astra (omp session)","priority":"P1","protocol_version":"0.1.0-draft","schema":"project-continuity.task.v1","status":"active","why":"PCM fail-closed delivery requires CI gates; repo has none, blocking ACS-0001 completion"} -->

- Status: active
- Owner: owner/Astra (omp session)
- Priority: P1
- Depends on: none

## Goal

Required ci status check on PRs to main, branch protection, auto-merge enabled; PCM issue-log-format marker sync

## Why

PCM fail-closed delivery requires CI gates; repo has none, blocking ACS-0001 completion

## Allowed files

- `.github/workflows/ci.yml` (new)
- `AGENTS.md`, `HANDOFF.md`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/task.md` (append `pcm:issue-log-format` marker block only)
- `checkpoints/CURRENT.md` (projection line)

## Human outcome

A fresh session resuming any task here can trust that "delivered" means machine-verified: every PR to `main` must pass a reproducible `ci` gate (continuity validate/preflight on a pinned public PCM install, tracked-secret scan, config-template parse, TypeScript syntax check), `main` cannot receive unverified pushes, and green PRs auto-merge without babysitting. ACS-0001/PR #4 becomes deliverable under the same discipline.

## Scope and boundaries

- In scope: ci workflow; `main` branch protection (`ci` required, no direct push); repo `allow_auto_merge`; issue-log-format 1.1.0 marker block in the 4 files 0.5.0 validate warns about.
- Out of scope: changing `oh-my-pi/` product behavior (ACS-0001); merging/closing #1/#2 (other task); force-push or history rewrite.
- Dependencies/uncertainty: CI pins `project-continuity` to public commit `743d50ede188eb0cd5457967a041880e2ff4cb31` (0.5.0; verified locally: pip git-install works, validate VALID, preflight TARGET_VALID). *Inferred:* solo-author repo → `required_approving_review_count: 0`; required-review discipline reduces to green `ci` + human merge intent.

## Acceptance criteria

- [ ] `gh pr checks` on this PR head shows `ci` pass.
- [ ] `main` protection reports required status check `ci` + push restriction; direct push rejected.
- [ ] This PR merges via auto-merge once `ci` is green (merge SHA recorded on #5).
- [ ] After rebase, `gh pr checks 4` shows `ci` green on ACS-0001 head.
- [ ] Pinned 0.5.0 `continuity validate` exits VALID with zero marker warnings.

## Evidence and sources

- Observed 2026-09-25 (local): `pip install git+https://github.com/Pukujan/project-continuity-modules.git@743d50e` → continuity 0.5.0; `validate --root .` → VALID + 4 marker warnings (AGENTS.md, HANDOFF.md, PR template, issue template); `preflight --root .` → TARGET_VALID exit 0. `node --check oh-my-pi/extensions/jev-court.ts` exit 0 (Node 24). Secret-scan regex clean. YAML/JSON config templates parse.
- Observed: `gh api .../branches/main/protection` → 404 "Branch not protected"; `gh pr checks 4` → "no checks reported" (2026-09-25, before this task).

## Reproduction details (only when needed)

Starting revision `1c44c8d` (main). Commands above; Python 3.12, Node 24.13.0, gh CLI authenticated as Pukujan.

## Related records

- Leaf: #5 (parent: none). Dependencies: none. Refs #3 (clears its blocker row).
- Primary writer: omp session (owner/Astra laptop) / branch `task/ACS-0002-ci-gates` / source issue: https://github.com/Pukujan/agent-custom-setup/issues/5 / as-of: opened 2026-09-25.
- PR/CI evidence + push receipt: see #5 comments and checkpoint below.

## Checkpoint log

No checkpoints yet.

### 2026-09-25 22:28:18 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["GitHub branch protection + auto-merge are post-push API operations; ci cannot report on any PR until the workflow exists on default branch or as head check \u2014 will verify checks on this PR head after push, then apply protection. PR #2 (other task, #1) will need branch refresh to inherit ci; not owned here."],"changed":[".github/workflows/ci.yml (new), AGENTS.md, HANDOFF.md, .github/pull_request_template.md, .github/ISSUE_TEMPLATE/task.md (marker block only), tasks/TASK-ACS-0002-ci-gates.md (new), checkpoints/CURRENT.md"],"completed":["ACS-0002 product delivered on task/ACS-0002-ci-gates: ci.yml (pinned continuity 0.5.0@743d50e validate+preflight, tracked secret scan, YAML/JSON template parse, node --check TS), issue-log-format 1.1.0 marker block appended to AGENTS/HANDOFF/PR template/issue template, TASK-ACS-0002 projection, CURRENT repointed. All gate steps pass locally (0.4.0 and 0.5.0 validate VALID; preflight TARGET_VALID; scan clean; 4 templates parse; jev-court.ts node --check exit 0)."],"decisions":["CI pins public commit 743d50e (0.5.0) \u2014 local 0.4.0 is an editable install of the source repo whose tree already declares 0.5.0; the published marker-block requirement originates from PCM 0.5.0, so validate/preflight run against the pinned public revision, not a floating version. Branch protection keeps required_approving_review_count=0 (solo author cannot self-approve; GitHub rejects >0 without at least one eligible reviewer) \u2014 machine gate ci is the enforcement; owner can raise later."],"evidence":["Product commit ef7c8cf; live issue #5 (leaf, parent none, deps none); #3 receipt published for docs head c3f7f91 (comment 5840410656); pip git-install of Pukujan/project-continuity-modules@743d50e verified in clean target (continuity 0.5.0)."],"next_action":"Push checkpoint; publish #5 receipt keyed to request id + pushed SHA; open PR to main with Refs #5; enable repo auto-merge and wait for ci; apply main protection (required check ci, restrict pushes); record merge SHA on #5.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0002","timestamp":"2026-09-25T22:28:18Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"3bbab76ddb1a9b8d9c93672b663c5ac392188316c7889170d22de6f8881dc5bb","request_id":"acs-0002-cigates-20260925","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0002"} -->

Completed:
- ACS-0002 product delivered on task/ACS-0002-ci-gates: ci.yml (pinned continuity 0.5.0@743d50e validate+preflight, tracked secret scan, YAML/JSON template parse, node --check TS), issue-log-format 1.1.0 marker block appended to AGENTS/HANDOFF/PR template/issue template, TASK-ACS-0002 projection, CURRENT repointed. All gate steps pass locally (0.4.0 and 0.5.0 validate VALID; preflight TARGET_VALID; scan clean; 4 templates parse; jev-court.ts node --check exit 0).

Evidence:
- Product commit ef7c8cf; live issue #5 (leaf, parent none, deps none); #3 receipt published for docs head c3f7f91 (comment 5840410656); pip git-install of Pukujan/project-continuity-modules@743d50e verified in clean target (continuity 0.5.0).

Decisions:
- CI pins public commit 743d50e (0.5.0) — local 0.4.0 is an editable install of the source repo whose tree already declares 0.5.0; the published marker-block requirement originates from PCM 0.5.0, so validate/preflight run against the pinned public revision, not a floating version. Branch protection keeps required_approving_review_count=0 (solo author cannot self-approve; GitHub rejects >0 without at least one eligible reviewer) — machine gate ci is the enforcement; owner can raise later.

Changed:
- .github/workflows/ci.yml (new), AGENTS.md, HANDOFF.md, .github/pull_request_template.md, .github/ISSUE_TEMPLATE/task.md (marker block only), tasks/TASK-ACS-0002-ci-gates.md (new), checkpoints/CURRENT.md

Blocked/uncertain:
- GitHub branch protection + auto-merge are post-push API operations; ci cannot report on any PR until the workflow exists on default branch or as head check — will verify checks on this PR head after push, then apply protection. PR #2 (other task, #1) will need branch refresh to inherit ci; not owned here.

Next:
- Push checkpoint; publish #5 receipt keyed to request id + pushed SHA; open PR to main with Refs #5; enable repo auto-merge and wait for ci; apply main protection (required check ci, restrict pushes); record merge SHA on #5.

### 2026-09-25 22:39:33 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["GitHub-hosted runner allocation for private-repo Actions on this account. Owner unblock options: add payment method / raise Actions spend limit, wait for monthly reset, attach a self-hosted runner, or make the repo public (2000 free Linux min/mo). Until then acceptance items 1-4 for ACS-0002 are unverifiable and ACS-0001 (PR #4) remains owner-review-only."],"changed":["checkpoints/CURRENT.md (blocker + next-action only)"],"completed":["CI runner blocker diagnosed and recorded (CURRENT Blockers row). Observed twice on PR #6 head d78486b: run 36196958507 jobs 108274881569 + rerun 108275962556 fail in ~2s with steps=[] and billable.total_ms=0; gh run view --log -> 'log not found'; actions/permissions enabled/all; runners 0; repo private. => job never gets a runner (Actions minutes/eligibility), not a workflow-content defect: identical gate commands pass locally on 0.4.0 and pinned 0.5.0."],"decisions":["Deliberately DEFER main branch protection + auto-merge until ci can actually pass: a required check that fails for capacity reasons freezes every merge (fail-closed discipline cuts both ways). Product (workflow + marker sync) stays pushed and reviewable at #6. *Inferred:* free private repos here have no included Linux minutes (or spend limit 0 / trial expired); owner must verify at github.com/settings/billing (gh token lacks user scope, endpoint 404)."],"evidence":["https://github.com/Pukujan/agent-custom-setup/actions/runs/36196958507 (conclusion failure x2 attempts, zero steps); gh api repos/Pukujan/agent-custom-setup/actions/runs/36196958507/timing -> billable UBUNTU total_ms 0; PR #6 head d78486ba2e7f406aa797d428a626ce11a073e658."],"next_action":"Owner: fix Actions capacity/eligibility, then re-run PR #6 checks (gh run rerun 36196958507 --failed) \u2014 expect ci green within minutes; then apply main protection (required check ci, enforce_admins=false, restrict_pushes=true, required_approving_review_count=0) and enable auto-merge on #6; after merge, rebase task/ACS-0001 onto gated main, confirm ci on #4, owner merges, close #3.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0002","timestamp":"2026-09-25T22:39:33Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"96f6605b9a1cc22623c8fdf3834faad1dd231c7b3f40a4bd156bf2cd3c7474b1","request_id":"acs-0002-blocker-20260925","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0002"} -->

Completed:
- CI runner blocker diagnosed and recorded (CURRENT Blockers row). Observed twice on PR #6 head d78486b: run 36196958507 jobs 108274881569 + rerun 108275962556 fail in ~2s with steps=[] and billable.total_ms=0; gh run view --log -> 'log not found'; actions/permissions enabled/all; runners 0; repo private. => job never gets a runner (Actions minutes/eligibility), not a workflow-content defect: identical gate commands pass locally on 0.4.0 and pinned 0.5.0.

Evidence:
- https://github.com/Pukujan/agent-custom-setup/actions/runs/36196958507 (conclusion failure x2 attempts, zero steps); gh api repos/Pukujan/agent-custom-setup/actions/runs/36196958507/timing -> billable UBUNTU total_ms 0; PR #6 head d78486ba2e7f406aa797d428a626ce11a073e658.

Decisions:
- Deliberately DEFER main branch protection + auto-merge until ci can actually pass: a required check that fails for capacity reasons freezes every merge (fail-closed discipline cuts both ways). Product (workflow + marker sync) stays pushed and reviewable at #6. *Inferred:* free private repos here have no included Linux minutes (or spend limit 0 / trial expired); owner must verify at github.com/settings/billing (gh token lacks user scope, endpoint 404).

Changed:
- checkpoints/CURRENT.md (blocker + next-action only)

Blocked/uncertain:
- GitHub-hosted runner allocation for private-repo Actions on this account. Owner unblock options: add payment method / raise Actions spend limit, wait for monthly reset, attach a self-hosted runner, or make the repo public (2000 free Linux min/mo). Until then acceptance items 1-4 for ACS-0002 are unverifiable and ACS-0001 (PR #4) remains owner-review-only.

Next:
- Owner: fix Actions capacity/eligibility, then re-run PR #6 checks (gh run rerun 36196958507 --failed) — expect ci green within minutes; then apply main protection (required check ci, enforce_admins=false, restrict_pushes=true, required_approving_review_count=0) and enable auto-merge on #6; after merge, rebase task/ACS-0001 onto gated main, confirm ci on #4, owner merges, close #3.

### 2026-09-25 22:40:31 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["GitHub-hosted runner allocation for private-repo Actions on this account. Owner unblock options: add payment method / raise Actions spend limit, wait for monthly reset, attach a self-hosted runner, or make the repo public (2000 free Linux min/mo). Until then ACS-0002 acceptance items 1-4 are unverifiable and ACS-0001 (PR #4) remains owner-review-only."],"changed":["checkpoints/CURRENT.md (blocker + next-action rows only); docs commit 9a4c1cf or current head"],"completed":["CI runner blocker diagnosed and recorded in CURRENT. Observed twice on PR #6 head d78486b: run 36196958507 jobs 108274881569 + rerun 108275962556 fail in ~2s with steps=[] and billable.total_ms=0; gh run view --log -> 'log not found'; actions/permissions enabled/all; runners 0; repo private. => job never gets a runner (Actions minutes/eligibility), not a workflow-content defect: identical gate commands pass locally on 0.4.0 and pinned 0.5.0."],"decisions":["Deliberately DEFER main branch protection + auto-merge until ci can actually pass: a required check that fails for capacity reasons freezes every merge (fail-closed discipline cuts both ways). Product (workflow + marker sync) stays pushed and reviewable at #6. *Inferred:* this private repo has no included Linux minutes (spend limit 0 or expired trial); owner verifies at github.com/settings/billing (gh token lacks user scope; billing endpoint 404)."],"evidence":["https://github.com/Pukujan/agent-custom-setup/actions/runs/36196958507 (conclusion failure x2 attempts, zero steps); gh api repos/Pukujan/agent-custom-setup/actions/runs/36196958507/timing -> billable UBUNTU total_ms 0; PR #6 head d78486ba2e7f406aa797d428a626ce11a073e658."],"next_action":"Owner fixes Actions capacity/eligibility; then gh run rerun 36196958507 --failed (expect ci green on #6); then apply main protection (required check ci, enforce_admins=false, restrict_pushes=true, required_approving_review_count=0) + auto-merge #6; after merge, rebase task/ACS-0001 onto gated main, confirm ci on #4, owner merges, close #3.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0002","timestamp":"2026-09-25T22:40:31Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"a492609ce04cb8b78e0b3b9e626bcb1df11632442bc56282ad2cf8a949783420","request_id":"acs-0002-blocker-b-20260925","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0002"} -->

Completed:
- CI runner blocker diagnosed and recorded in CURRENT. Observed twice on PR #6 head d78486b: run 36196958507 jobs 108274881569 + rerun 108275962556 fail in ~2s with steps=[] and billable.total_ms=0; gh run view --log -> 'log not found'; actions/permissions enabled/all; runners 0; repo private. => job never gets a runner (Actions minutes/eligibility), not a workflow-content defect: identical gate commands pass locally on 0.4.0 and pinned 0.5.0.

Evidence:
- https://github.com/Pukujan/agent-custom-setup/actions/runs/36196958507 (conclusion failure x2 attempts, zero steps); gh api repos/Pukujan/agent-custom-setup/actions/runs/36196958507/timing -> billable UBUNTU total_ms 0; PR #6 head d78486ba2e7f406aa797d428a626ce11a073e658.

Decisions:
- Deliberately DEFER main branch protection + auto-merge until ci can actually pass: a required check that fails for capacity reasons freezes every merge (fail-closed discipline cuts both ways). Product (workflow + marker sync) stays pushed and reviewable at #6. *Inferred:* this private repo has no included Linux minutes (spend limit 0 or expired trial); owner verifies at github.com/settings/billing (gh token lacks user scope; billing endpoint 404).

Changed:
- checkpoints/CURRENT.md (blocker + next-action rows only); docs commit 9a4c1cf or current head

Blocked/uncertain:
- GitHub-hosted runner allocation for private-repo Actions on this account. Owner unblock options: add payment method / raise Actions spend limit, wait for monthly reset, attach a self-hosted runner, or make the repo public (2000 free Linux min/mo). Until then ACS-0002 acceptance items 1-4 are unverifiable and ACS-0001 (PR #4) remains owner-review-only.

Next:
- Owner fixes Actions capacity/eligibility; then gh run rerun 36196958507 --failed (expect ci green on #6); then apply main protection (required check ci, enforce_admins=false, restrict_pushes=true, required_approving_review_count=0) + auto-merge #6; after merge, rebase task/ACS-0001 onto gated main, confirm ci on #4, owner merges, close #3.

## Handoff

Read PROJECT → CURRENT → this task → minimum relevant spec. Checkpoint before stopping.
