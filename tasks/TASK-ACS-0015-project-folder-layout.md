# TASK-ACS-0015 — Accept the project-folder layout in dev_root_check

<!-- continuity:task {"acceptance": ["dev_root_check.py accepts legacy flat checkouts and project folders (<project>/main + optional <project>/worktrees/ of linked worktrees of that main)", "inside a project folder it flags extra entries, foreign worktrees, non-worktree clones under worktrees/, and the repo's worktrees registered in the dev root outside <project>/worktrees/", "--clean respects the layout and --migrate <repo> plans flat-to-project moves, acting only with --yes and refusing dirty, unpushed or stashed work", "HOTLOAD.md, BEHAVIOR.md and the PROMPT_INJECT ACS section describe the project folder as the preferred form", "check_pins.py exits OK and the hotloader pack tests pass on the candidate", "PCM delivery: PR Closes #74"], "depends_on": [], "goal": "Make <project>/main plus <project>/worktrees/<task> the preferred dev root layout and teach dev_root_check to check, clean and migrate to it.", "id": "ACS-0015", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/74", "next_action": "Push the branch, open the PR (Closes #74), and confirm gates.", "owner": "owner/Pukujan (Grok Bot session)", "priority": "P2", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "active", "why": "Owner direction 2026-10-04: each repo gets one project folder with main/ and worktrees/ inside it; worktrees never sit beside or inside the main checkout. PCM side: Pukujan/project-continuity-modules#234."} -->

- Status: active
- Owner / primary writer: owner/Pukujan (Grok Bot session)
- Priority: P2
- Depends on: none
- Leaf owning issue: [#74](https://github.com/Pukujan/agent-custom-setup/issues/74)
- Related: Pukujan/project-continuity-modules#234 (PCM managed worktrees)
- Branch: `task/ACS-project-folder-layout`

## Goal

Each repo gets one project folder in the dev root: the primary checkout at
`<project>/main` and task worktrees at `<project>/worktrees/<task>`. A legacy
flat checkout stays accepted. Dependency clones, scratch and caches stay in the
ACS cache outside the dev root.

## Allowed files

- `modules/coordination/multi-agent-hotload/v0.1.0/{HOTLOAD,BEHAVIOR,PROMPT_INJECT,README}.md`
- `modules/coordination/multi-agent-hotload/v0.1.0/scripts/{hotload_check,dev_root_check}.py`
- `modules/coordination/multi-agent-hotload/v0.1.0/tests/test_dev_root_check.py`
- `tasks/TASK-ACS-0015-*.md`, `checkpoints/CURRENT.md`

## Non-goals

- No PCM code; PCM's worktree placement is tracked in PCM #234.
- No migration of real repos on the owner's PC as part of this task.

## Next atomic action

Push the branch, open the PR (Closes #74), and confirm `gates`.

## Checkpoint log

### 2026-10-04 — project-folder layout (as-of; live issues own progression)

Completed:
- `dev_root_check.py` accepts project folders and flat checkouts, adds the
  project-folder findings, moves a project's misplaced worktrees home under
  `--clean`, and adds `--migrate <repo>`.
- Rule text updated in HOTLOAD.md, BEHAVIOR.md and the PROMPT_INJECT ACS section.

Evidence:
- `check_pins.py` OK; pack tests run with uv on the Windows checkout (results on the PR).

Decisions:
- A project's own worktree in the wrong place is moved with `git worktree move`
  rather than removed, because moving keeps any uncommitted work.
- `--migrate` renames the checkout through a temporary name and runs
  `git worktree repair` before moving worktrees.

Blocked/uncertain:
- None.

Next: push the branch, open the PR (Closes #74), confirm `gates`.
