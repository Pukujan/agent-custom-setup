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

## Handoff

Read PROJECT → CURRENT → this task → minimum relevant spec. Checkpoint before stopping.
