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

- [ ] `gh pr checks` on this PR head shows the check (context `gates` — job id; add `name: ci` to the job if a stable `ci` context is wanted) pass.
- [ ] `main` protection requires status check `gates` and rejects direct pushes (`enforce_admins=true`; `restrict_pushes` availability on this plan = observe at apply time).
- [ ] This PR merges via auto-merge once the check is green (merge SHA recorded on #5).
- [ ] After syncing ACS-0001 by merging main into it (append-only; no rebase/force-push), `gh pr checks 4` shows the check green on the new head.
- [ ] Pinned 0.5.0 `continuity validate` exits VALID with zero marker warnings.

## Evidence and sources

- Observed 2026-09-25 (local): `pip install git+https://github.com/Pukujan/project-continuity-modules.git@743d50e` → continuity 0.5.0; `validate --root .` → VALID + 4 marker warnings (AGENTS.md, HANDOFF.md, PR template, issue template); `preflight --root .` → TARGET_VALID exit 0. `node --check oh-my-pi/extensions/jev-court.ts` exit 0 (Node 24). Secret-scan regex clean. YAML/JSON config templates parse.
- Observed 2026-09-25 (correction/supersession for the checkpoint-log wording "public gives 2000 free Linux min/mo" in request `acs-0002-blocker-b-20260925` — figures were inverted): public sibling `Pukujan/project-continuity-modules` Actions = 387 runs, latest push run success 22:59Z → Actions healthy account-wide; this failure is private-repo runner allocation.
- Verified 2026-09-26T00:1Z by direct primary-page fetch (read tool, .md rendering): (a) https://docs.github.com/en/billing/concepts/product-billing/github-actions verbatim — Free = 2,000 Actions min/month, Pro = 3,000 (private quota); "The use of standard GitHub-hosted runners is free… In public repositories"; "If your account does not have a valid payment method on file, usage is blocked once you use up your quota". (b) https://docs.github.com/en/get-started/learning-about-github/githubs-plans — Free personal: private repos "with a limited feature set"; Pro adds "Advanced tools and insights in private repositories: … Protected branches". Append-only correction: the 23:5Z line attributed (b) to about-protected-branches, which contains NO plan text — wrong page, now fixed. (c) account plan UNOBSERVED (`gh api user` .plan.name empty; billing API needs user scope) → protection feasibility = owner-checkable fact, not inferred. (d) closing keywords: PR body + commit messages only (comments excluded); colon form official; fires on merge to default branch (linking-a-pull-request-to-an-issue, fetched 23:5Z). Acceptance items 2-3 stand plan-gated; owner options unchanged (public / upgrade Pro / record plan-blocked).

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

### 2026-09-25 23:22:12 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["Unchanged root blocker: private-repo Actions runner allocation; owner checks github.com/settings/billing (spend limit/usage; token lacks user scope for API read), or monthly reset, or self-hosted runner, or public conversion (also clears reported plan-eligibility concern for private-repo protection). Protection+auto-merge remain deliberately deferred until the check can pass."],"changed":["checkpoints/CURRENT.md (Blockers, Next atomic action), tasks/TASK-ACS-0002-ci-gates.md (Acceptance context names; Evidence supersession line)"],"completed":["Blocker record corrected and superseded (docs-only increment c9ae9f8 on top of d78486b/7488996): (1) facts \u2014 account-wide Actions verified healthy via public sibling Pukujan/project-continuity-modules (387 runs; latest push run completed/success 2026-09-25T22:59Z), so the zero-step/zero-billable failure is private-repo runner allocation; earlier 'public gives 2000 free min / private has no included minutes' wording was inverted vs GitHub billing docs (reported: Free = 2,000 private Linux min/month account-wide; public repos unmetered on standard runners). (2) required-check context \u2014 observed 'gates' in gh pr checks 6 (job id; workflow name 'ci' is not the context); CURRENT next-action + task acceptance reworded to gates with optional name: ci upgrade. (3) protection next-step \u2014 enforce_admins=true so direct-push rejection is real; restrict_pushes and private-repo protection/rulesets plan eligibility marked observe-at-apply (reported Pro/Team/Enterprise; unverified at source)."],"decisions":["Supersession recorded as append-only correction per PCM (checkpoint history not rewritten); the acs-0002-blocker-b evidence line in tasks/TASK-ACS-0002-ci-gates.md carries the inverted-figures correction text. Deferred without change: ci.yml content (probe inconclusive \u2014 public-sibling success proves workflow-file health for public repos; private block remains the open hypothesis), repo visibility/plan decisions are owner-side."],"evidence":["gh api repos/Pukujan/project-continuity-modules/actions/runs -> total_count 387, latest push success 22:58:51Z completed/success 22:59Z (observed 2026-09-25); gh pr checks 6 -> context 'gates' fail (observed 22:29Z); run 36196958507 attempts 1-2: steps=[] billable.total_ms=0 (observed). continuity validate VALID pre-commit. Product SHAs unchanged (ci.yml ef7c8cf)."],"next_action":"Publish #5 correction receipt + #3 linked progression update for c9ae9f8/this checkpoint SHA; then owner unblocks Actions; then gh run rerun 36196958507 --failed, require context 'gates' (or add job name: ci and re-check), enforce_admins=true, auto-merge #6.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0002","timestamp":"2026-09-25T23:22:12Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"67a8e38f6aaf022c33e3696f5b58353229b271b98d62343138de49ec429ac955","request_id":"acs-0002-correction-20260925","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0002"} -->

Completed:
- Blocker record corrected and superseded (docs-only increment c9ae9f8 on top of d78486b/7488996): (1) facts — account-wide Actions verified healthy via public sibling Pukujan/project-continuity-modules (387 runs; latest push run completed/success 2026-09-25T22:59Z), so the zero-step/zero-billable failure is private-repo runner allocation; earlier 'public gives 2000 free min / private has no included minutes' wording was inverted vs GitHub billing docs (reported: Free = 2,000 private Linux min/month account-wide; public repos unmetered on standard runners). (2) required-check context — observed 'gates' in gh pr checks 6 (job id; workflow name 'ci' is not the context); CURRENT next-action + task acceptance reworded to gates with optional name: ci upgrade. (3) protection next-step — enforce_admins=true so direct-push rejection is real; restrict_pushes and private-repo protection/rulesets plan eligibility marked observe-at-apply (reported Pro/Team/Enterprise; unverified at source).

Evidence:
- gh api repos/Pukujan/project-continuity-modules/actions/runs -> total_count 387, latest push success 22:58:51Z completed/success 22:59Z (observed 2026-09-25); gh pr checks 6 -> context 'gates' fail (observed 22:29Z); run 36196958507 attempts 1-2: steps=[] billable.total_ms=0 (observed). continuity validate VALID pre-commit. Product SHAs unchanged (ci.yml ef7c8cf).

Decisions:
- Supersession recorded as append-only correction per PCM (checkpoint history not rewritten); the acs-0002-blocker-b evidence line in tasks/TASK-ACS-0002-ci-gates.md carries the inverted-figures correction text. Deferred without change: ci.yml content (probe inconclusive — public-sibling success proves workflow-file health for public repos; private block remains the open hypothesis), repo visibility/plan decisions are owner-side.

Changed:
- checkpoints/CURRENT.md (Blockers, Next atomic action), tasks/TASK-ACS-0002-ci-gates.md (Acceptance context names; Evidence supersession line)

Blocked/uncertain:
- Unchanged root blocker: private-repo Actions runner allocation; owner checks github.com/settings/billing (spend limit/usage; token lacks user scope for API read), or monthly reset, or self-hosted runner, or public conversion (also clears reported plan-eligibility concern for private-repo protection). Protection+auto-merge remain deliberately deferred until the check can pass.

Next:
- Publish #5 correction receipt + #3 linked progression update for c9ae9f8/this checkpoint SHA; then owner unblocks Actions; then gh run rerun 36196958507 --failed, require context 'gates' (or add job name: ci and re-check), enforce_admins=true, auto-merge #6.

### 2026-09-25 23:57:43 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["Unchanged root: private-repo runner allocation (plan/spend state unobservable without user scope). NEW verified constraint: even with capacity, branch protection on private requires Pro+."],"changed":["checkpoints/CURRENT.md, tasks/TASK-ACS-0002-ci-gates.md (provenance + sync wording)"],"completed":["Verified external research replaces inference in ACS-0002 records: docs.github.com billing + protected-branches pages fetched and cited (Free=2,000 private min/mo account-wide, Pro=3,000, public standard runners free; private-repo protected branches need Pro/Team/Enterprise). Consequence recorded: acceptance items 2-3 are plan-gated, owner options = public conversion / upgrade / record plan-blocked. Merge-not-rebase sync decision recorded (advisor-caught contradiction: bodies promised no-history-rewrite while plans said rebase). Closing-keyword surfaces confirmed at source (PR body + commit messages; comments not in scope) -> hazard narrative consolidated on issue comments, PR #4 body kept minimal."],"decisions":["Owner direction (this session): use spec-driven external research with provenance, and omp -p headless sessions for differential/iterative README evaluation (see #7) \u2014 gates must be machine-checked against primary specs, not advisor summaries."],"evidence":["web_search fetch 2026-09-25T23:5Z: docs.github.com/en/billing/concepts/product-billing/github-actions; docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches; docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue. Live body audits: PR4/6/8 zero keyword-adjacent-number hits (colon-aware grep). PR4 live grep 'rebase' = none. continuity validate VALID pre-commit."],"next_action":"On ACS-0003 branch: build hidden-holdout + metamorphic + baseline-vs-current differential eval per CGM HOLDOUT_EVALUATION/TDD docs using omp -p --no-tools --no-session arms; iterate README on failures; checkpoint + #7 receipt.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0002","timestamp":"2026-09-25T23:57:43Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"a013fbc44bd8e8a7191540e9e71e122ed97eef22d18066ef172696c810df5aba","request_id":"acs-0002-plangate-20260926","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0002"} -->

Completed:
- Verified external research replaces inference in ACS-0002 records: docs.github.com billing + protected-branches pages fetched and cited (Free=2,000 private min/mo account-wide, Pro=3,000, public standard runners free; private-repo protected branches need Pro/Team/Enterprise). Consequence recorded: acceptance items 2-3 are plan-gated, owner options = public conversion / upgrade / record plan-blocked. Merge-not-rebase sync decision recorded (advisor-caught contradiction: bodies promised no-history-rewrite while plans said rebase). Closing-keyword surfaces confirmed at source (PR body + commit messages; comments not in scope) -> hazard narrative consolidated on issue comments, PR #4 body kept minimal.

Evidence:
- web_search fetch 2026-09-25T23:5Z: docs.github.com/en/billing/concepts/product-billing/github-actions; docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches; docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue. Live body audits: PR4/6/8 zero keyword-adjacent-number hits (colon-aware grep). PR4 live grep 'rebase' = none. continuity validate VALID pre-commit.

Decisions:
- Owner direction (this session): use spec-driven external research with provenance, and omp -p headless sessions for differential/iterative README evaluation (see #7) — gates must be machine-checked against primary specs, not advisor summaries.

Changed:
- checkpoints/CURRENT.md, tasks/TASK-ACS-0002-ci-gates.md (provenance + sync wording)

Blocked/uncertain:
- Unchanged root: private-repo runner allocation (plan/spend state unobservable without user scope). NEW verified constraint: even with capacity, branch protection on private requires Pro+.

Next:
- On ACS-0003 branch: build hidden-holdout + metamorphic + baseline-vs-current differential eval per CGM HOLDOUT_EVALUATION/TDD docs using omp -p --no-tools --no-session arms; iterate README on failures; checkpoint + #7 receipt.

## Handoff

Read PROJECT → CURRENT → this task → minimum relevant spec. Checkpoint before stopping.
