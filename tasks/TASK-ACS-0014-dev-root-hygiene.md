# TASK-ACS-0014 — Keep the dev root to one main checkout per repo

<!-- continuity:task {"acceptance": ["HOTLOAD.md, BEHAVIOR.md and the generated PROMPT_INJECT.md state the dev root rule and the cache locations", "scripts/dev_root_check.py flags non-git folders, dot/underscore folders, linked worktrees, duplicate clones and registered worktrees under the dev root, prints JSON and exits non-zero on findings", "dev_root_check.py --clean is a dry run without --yes and refuses repos with dirty, unpushed or stashed work", "hotload_check.py warns on dev root findings (fails with --strict-dev-root) and refuses dependency checkouts inside the dev root", "check_pins.py exits OK and the hotloader pack tests pass on the candidate", "PCM delivery: PR Closes #71"], "depends_on": [], "goal": "State and enforce that the dev root holds one main checkout per repo, with worktrees, dependency clones, scratch and caches under the per-user ACS cache.", "id": "ACS-0014", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/71", "next_action": "Push the branch, open the PR (Closes #71), and confirm gates.", "owner": "owner/Pukujan (Grok Bot session)", "priority": "P2", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "active", "why": "D:\\development filled up with _deps, .scratch, acs-helpers copies and stray worktrees because nothing in the hotloader said where that work should live."} -->

- Status: active
- Owner / primary writer: owner/Pukujan (Grok Bot session)
- Priority: P2
- Depends on: none
- Leaf owning issue: [#71](https://github.com/Pukujan/agent-custom-setup/issues/71)
- Branch: `task/ACS-dev-root-hygiene`

## Goal

The dev root (`ACS_DEV_ROOT`, default `D:\development` on Windows and
`~/development` elsewhere) holds one main checkout per repo. Worktrees,
dependency clones, scratch work and caches go under the ACS cache
(`%LOCALAPPDATA%\acs\{deps,scratch,worktrees}` on Windows,
`~/.cache/acs/...` on macOS and Linux).

## Allowed files

- `modules/coordination/multi-agent-hotload/v0.1.0/{HOTLOAD,BEHAVIOR,PROMPT_INJECT,README}.md`, `module.json`
- `modules/coordination/multi-agent-hotload/v0.1.0/scripts/{hotload_check,dev_root_check}.py`
- `modules/coordination/multi-agent-hotload/v0.1.0/tests/test_dev_root_check.py`
- `tasks/TASK-ACS-0014-*.md`, `checkpoints/CURRENT.md`

## Non-goals

- No change to the PCM/CGM pins and no edit to CGM's `system_block`; the rule
  ships as an ACS-owned addendum next to it.
- `--clean` never deletes work: it refuses anything with uncommitted, unpushed
  or stashed changes and moves the rest into the cache.

## Next atomic action

Push the branch, open the PR (Closes #71), and confirm `gates`.

## Checkpoint log

### 2026-10-04 — dev root rule + checker (as-of; live issues own progression)

Completed:
- Wrote the rule into `HOTLOAD.md` and `BEHAVIOR.md`, and added it as an
  ACS-owned addendum to the rendered `PROMPT_INJECT.md`.
- Added `scripts/dev_root_check.py` (scan + `--clean` dry run / `--yes`) and
  wired it into `hotload_check.py` as a warning, or a failure with
  `--strict-dev-root`. Pinned CGM discovery now tries `<cache>/deps/` first and
  skips copies inside the dev root.
- Added `tests/test_dev_root_check.py` (fake dev roots under `tmp_path`).

Evidence:
- `check_pins.py` OK (15 projections agree); `continuity validate` VALID;
  pack tests run with uv on the Windows checkout (results on the PR).

Decisions:
- The rule ships as an ACS addendum next to CGM's `system_block` rather than an
  edit to CGM, which ACS pins but does not own.
- `--clean` moves rather than deletes, except for linked worktrees (removed via
  git) and top-level tool caches.

Blocked/uncertain:
- None.

Next: push the branch, open the PR (Closes #71), confirm `gates`.
