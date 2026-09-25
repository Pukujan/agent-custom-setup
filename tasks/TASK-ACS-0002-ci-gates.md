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

## Handoff

Read PROJECT → CURRENT → this task → minimum relevant spec. Checkpoint before stopping.
