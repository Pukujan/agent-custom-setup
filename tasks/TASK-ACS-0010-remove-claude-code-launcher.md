# TASK-ACS-0010 — Remove the Claude Code launcher from ACS

<!-- continuity:task {"acceptance": ["no modules/claude-code/inferhub-litellm* directory remains", "registry.json has no inferhub-litellm entry and still parses", "live docs (modules/claude-code/SETUP.md, HOW-IT-WORKS.md, POLICY.md) point to Pukujan/claude-code-launcher", "required gates check passes on the PR", "draft PR Refs #66 waits on Alex's OK and the new repo's launcher PRs"], "depends_on": [], "goal": "Remove the Claude Code + InferHub launcher module from ACS and point readers to Pukujan/claude-code-launcher, where it now lives.", "id": "ACS-0010", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/66", "next_action": "Alex reviews the draft PR; once he approves and the new repo's launcher PRs are merged, mark it ready, merge, then close PR #65 and post the #64 and #9 comments from the PR body.", "owner": "Grok Bot (executor agent for Alex)", "priority": "P2", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "active", "why": "The launcher now has its own repo. A second, older copy in ACS looks authoritative but is already behind, so people would deploy the wrong one."} -->

- Status: active
- Owner / primary writer: Grok Bot (executor agent for Alex)
- Priority: P2
- Depends on: Alex's OK; the launcher PRs in Pukujan/claude-code-launcher merging
- Leaf owning issue: [#66](https://github.com/Pukujan/agent-custom-setup/issues/66)
- Parent ancestry: none (related: #9, #64, PR #65)
- Branch: `task/ACS-0010-remove-claude-code-launcher`

## Goal

The Claude Code + InferHub launcher moved to its own private repo,
[Pukujan/claude-code-launcher](https://github.com/Pukujan/claude-code-launcher).
This task deletes the old `inferhub-litellm` module from ACS, drops its
`registry.json` entry, and leaves a short pointer to the new repo in the docs
that used to describe it.

## Allowed files

- `modules/claude-code/inferhub-litellm/**` (removed)
- `modules/claude-code/SETUP.md`, `modules/claude-code/HOW-IT-WORKS.md`
- `registry.json`, `POLICY.md`
- `checkpoints/CURRENT.md`, `tasks/TASK-ACS-0010-*.md` (this record)

## Non-goals

- No changes to Pukujan/claude-code-launcher.
- Historical records stay untouched: older task logs, eval variants under
  `evals/variants/`, and captured transcripts/fixtures under
  `modules/coordination/jev-oss-compare/`.
- No closing of PR #65 or comments on #64 / #9 until Alex says so.

## Evidence

- Repo-wide grep for `inferhub-litellm`, `launch-claude-inferhub` and
  `claude-code/` after the change: only historical records match (see the PR
  body for the list).
- Local run of the CI gate steps (continuity 0.6.0 validate + preflight, pin
  drift check, hotload pack tests, secret scan): see the PR.

## Checkpoint log

