# TASK-ACS-0005 — OMP Loop Hardening

<!-- continuity:task {"acceptance": ["patched extensions load in installed omp v18.4.4 (scratch -e runs) with no load errors", "offline fixture replay: 94 #35 notes -> 0 deliveries under fail-quiet default; revival/budget paths exercised", "omp config get: syncBacklog=3 (enum type fixed), immuneTurns=6, maxNotesPerUpdate=2, goal.continuationModes=[], todo.remindersMax=1 — live observed", "live cutover with dated backup; owner model-role drift preserved", "PCM delivery: checkpoint + #37 receipt + PR Refs #35 #37"], "depends_on": [], "goal": "Stop omp advisory looping: jev-court v2 (fail-quiet, budgets, no-wake delivery, stop-aware, durable decisions), new loop-guard (replay marking, task-echo guidance), silence-first roster, and storm config fixes, installed on the owner's live agent dir", "id": "ACS-0005", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/37", "next_action": "Owner review + merge the ACS-0005 PR (Refs #35 #37); then confirm in a fresh live session (court disabled at start, no post-settle advisory wakes) and append the delivery receipt to #37", "owner": "owner/Astra (omp session)", "priority": "P0", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "active", "why": "Owner: OMP is currently unusable — sessions spend turns reacting to injected advisories, replays, and reminders instead of the primary task and never finish (#35). Parent intake: issue #35; this task's leaf issue is #37."} -->

- Status: active
- Owner / primary writer: owner/Astra (omp session)
- Priority: P0
- Depends on: none (parent intake issue #35 is a scope source, not a blocker)
- Leaf owning issue: [#37](https://github.com/Pukujan/agent-custom-setup/issues/37)
- Parent ancestry: [#35](https://github.com/Pukujan/agent-custom-setup/issues/35) (intake); dependencies: none
- Branch: `task/ACS-0005-omp-loop-hardening`

## Goal

Stop the harness-level looping described in #35: jev-court's advisory storm (83 injected messages vs ~11 native advisory cards in the #35 session), silently-inert storm config (`syncBacklog: 1` numeric → enum-validation failure → `off`), unbounded two-advisor roster (94 notes/session, scope = blocker factory), reminder/goal re-injection after owner stop, and subagent delivery failures. Rewrite `jev-court` (v2: fail-quiet, budgets, no-wake delivery, stop suppression, transcript reconciliation, durable decisions), add `loop-guard` (async-result replay marking, task-echo detection), harden `WATCHDOG.yml` + `config.yml`, and install on the owner's live `~/.omp/agent/` (with dated backup).

## Why

Owner report 2026-09-29: sessions spend turns reacting to injected messages instead of the primary task and never reach a visible end. Measured diagnosis on the live fixture: the court bypassed every harness storm control (steer/aside wake semantics, per-update budgets, immuneTurns, stop suppression), its least-confident verdict (`insufficient_evidence`) was the only unthresholded delivery branch, and its dedupe memory did not survive restarts while its persisted ledger was never read back.

## Allowed files

- `oh-my-pi/extensions/jev-court.ts` (v2 rewrite), `oh-my-pi/extensions/loop-guard.ts` (new)
- `oh-my-pi/config/config.yml`, `oh-my-pi/config/WATCHDOG.yml`, `oh-my-pi/config/jev-court.example.json`
- `oh-my-pi/README.md`, `checkpoints/CURRENT.md`, `tasks/TASK-ACS-0005-omp-loop-hardening.md`, `.gitignore`
- (`oh-my-pi/config/models.yml` carries the owner's uncommitted plan-role drift — preserved, not ours)

## Non-goals

- No omp-core changes. Upstream residue: async-result wake dedup (marking is in-repo; the wake is harness-owned), stop-aware cancellation of `todo_reminder`/`goal_updated` (notification-only events in v18.4.4).

## Evidence

- Issue #37 body: measured fixture counts, config-key verification, v1 code defects (line-referenced).
- Verification: real-code replay of the #35 fixture under node (32/32 assertions; v1's 83-message storm → 0 injections on the real primary transcript); clean load in the installed `omp` v18.4.4 (`omp -p` scratch run); `omp config get` post-cutover values.

## Next atomic action

Owner review + merge the PR (Refs #35 #37); then fresh-live-session confirmation (court disabled at start, no post-settle advisory wakes) and the delivery receipt on #37.

## Checkpoint log
