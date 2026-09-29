# TASK-ACS-0005 — OMP Loop Hardening

<!-- continuity:task {"acceptance": ["patched extensions load in installed omp v18.4.4 (scratch -e runs) with no load errors", "offline fixture replay: 94 #35 notes -> 0 deliveries under fail-quiet default; revival/budget paths exercised", "omp config get: syncBacklog=3 (enum type fixed), immuneTurns=6, maxNotesPerUpdate=2, goal.continuationModes=[], todo.remindersMax=1 — live observed", "live cutover with dated backup; owner model-role drift preserved", "PCM delivery: checkpoint + #37 receipt + PR Refs #35 #37"], "id": "ACS-0005", "issue": "https://github.com/Pukujan/agent-custom-setup/issues/37", "parent": "https://github.com/Pukujan/agent-custom-setup/issues/35", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1"} -->

- Status: in_progress
- Owner: owner/Astra (omp session)
- Priority: P0 (owner: "OMP is currently being unusable")
- Depends on: none
- Issue: #37 (leaf); parent #35 (intake)
- Branch: `task/ACS-0005-omp-loop-hardening`

## Goal

Stop the harness-level looping described in #35: jev-court's advisory storm (83 injected messages vs ~11 native cards in the #35 session), silently-inert storm config (`syncBacklog: 1` numeric → enum-validation failure → `off`), unbounded two-advisor roster (94 notes/session, scope = blocker factory), reminder/goal re-injection after owner stop, and subagent delivery failures. Rewrite `jev-court` (v2: fail-quiet, budgets, no-wake delivery, stop suppression, transcript reconciliation, durable decisions), add `loop-guard` (async-result replay marking, task-echo detection), harden `WATCHDOG.yml` + `config.yml`, and install on the owner's live `~/.omp/agent/` (with dated backup).

## Why

Owner report 2026-09-29: sessions spend turns reacting to injected advisories/replays instead of the primary task and never finish. Measured diagnosis on the live fixture: the court bypassed every harness storm control (steer/aside wake semantics, per-update budgets, immuneTurns, stop suppression), its least-confident verdict (`insufficient_evidence`) was the only unthresholded delivery branch, and its dedupe memory did not survive restarts while its persisted ledger was never read back.

## Allowed files

- `oh-my-pi/extensions/jev-court.ts` (v2 rewrite), `oh-my-pi/extensions/loop-guard.ts` (new)
- `oh-my-pi/config/config.yml`, `oh-my-pi/config/WATCHDOG.yml`, `oh-my-pi/config/jev-court.example.json`
- `oh-my-pi/README.md`, `checkpoints/CURRENT.md`, `tasks/TASK-ACS-0005-omp-loop-hardening.md`
- (`oh-my-pi/config/models.yml` carries the owner's uncommitted plan-role drift — preserved, not ours)

## Non-goals

- No omp-core changes. Upstream residue: async-result wake dedup (marking is in-repo; the wake is harness-owned), stop-aware cancellation of `todo_reminder`/`goal_updated` (notification-only events in v18.4.4).

## Evidence

- Issue #37 body: measured fixture counts, config-key verification, v1 code defects (line-referenced).
- Verification commands: scratch `omp -p -e` load runs; offline 94-note replay; `omp config get` post-cutover.

## Next atomic action

Verify (load + replay + config get), install live, checkpoint, push, PR `Refs #35 #37`, issue receipt.
