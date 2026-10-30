# TASK-ACS-0054 — Put the hotload rules in front of Claude Code

<!-- continuity:task {"acceptance": ["acs_install.py writes CLAUDE.md with an @AGENTS.md line and an acs:boot block in AGENTS.md (HOTLOAD.md pointer, CGM always-on writing block, dev-root rule), idempotently and without touching content outside the markers", "hotload_check.py exits non-zero for an installed adopter whose CLAUDE.md import or AGENTS.md block is missing", "new tests in tests/test_agent_wiring.py fail before the change and pass after; hotloader pack tests and check_pins.py pass", "PCM delivery: draft PR Refs #112 (never closes it)"], "depends_on": [], "goal": "Make the installer wire the hotload rules into CLAUDE.md and AGENTS.md so a Claude Code session in an adopter sees them, and make hotload_check fail when that wiring is absent.", "id": "ACS-0054", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/112", "next_action": "Wait for green gates on the draft PR, then let the owner decide on merge and on the out-of-scope items (watchdog workflow, hook).", "owner": "owner/Pukujan (Claude Code session)", "priority": "P2", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "active", "why": "After the 2026-10-21 install, agents in an adopter followed only the issue-log rule: no CLAUDE.md existed and nothing pointed at HOTLOAD.md, the always-on writing block or the dev-root rule (issue #112)."} -->

- Status: active
- Owner / primary writer: owner/Pukujan (Claude Code session)
- Priority: P2
- Depends on: none
- Leaf owning issue: [#112](https://github.com/Pukujan/agent-custom-setup/issues/112) (parent: none)
- Branch: `task/ACS-0054-claude-wiring`

## Goal

An install leaves the adopter with `CLAUDE.md` importing `AGENTS.md` and a managed
`acs:boot` block in `AGENTS.md`; `hotload_check.py` refuses an installed adopter
without them.

## Allowed files

- `modules/coordination/multi-agent-hotload/v0.1.0/scripts/{acs_install,hotload_check}.py`
- `modules/coordination/multi-agent-hotload/v0.1.0/tests/test_agent_wiring.py`
- `modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md`
- `tasks/TASK-ACS-0054-*.md`, `checkpoints/CURRENT.md`

## Non-goals

- Watchdog workflow install and agent-less watchdog schedule (issue #112 symptom 3; separate consent, CI cost).
- Stale seat, checkpoint freshness and dev-root clutter detection beyond the existing warnings.
- A `SessionStart` hook in the adopter's `.claude/settings.json`: skipped, `@AGENTS.md` already puts the block in front of Claude Code.
- The PCM/CGM first-install deadlocks tracked in #61. Issue #112 stays open.

## Next atomic action

Wait for green `gates` on the draft PR (Refs #112), then hand the merge decision to the owner.

## Checkpoint log

### 2026-10-30 — wiring implemented (as-of; live issues own progression)

Completed: installer writes the wiring; `hotload_check` enforces it; 12 new tests.
Evidence: see the PR description for test output.
Blocked/uncertain: `continuity validate` was not run locally (the PCM CLI was not installed in this session); CI runs it.
Next: green `gates` on the draft PR.
