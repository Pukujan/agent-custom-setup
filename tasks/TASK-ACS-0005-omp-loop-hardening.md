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

### 2026-09-29 21:37:56 UTC — omp/qwen3.8-flash

<!-- continuity:checkpoint {"agent":"omp/qwen3.8-flash","blocked":[],"changed":["oh-my-pi/extensions/jev-court.ts, oh-my-pi/extensions/loop-guard.ts, oh-my-pi/config/{config.yml,WATCHDOG.yml,jev-court.example.json}, oh-my-pi/README.md, tasks/TASK-ACS-0005-omp-loop-hardening.md, checkpoints/CURRENT.md"],"completed":["jev-court v2 rewrite (fail-quiet, budgets, nextTurn-when-idle, stop suppression, transcript reconciliation, re-raise reuse, durable rehydrated decisions); new loop-guard (replay marking, task-echo guidance); WATCHDOG silence-first + scope disabled; config storm keys incl. syncBacklog enum-type fix; README/CURRENT/task projection updated; live ~/.omp/agent cutover with dated backup"],"decisions":["scope advisor disabled pending hardened severity rules; court opt-in default; goal auto-continue off; upstream residue documented (async-result wake, notification-only reminder events)"],"evidence":["32/32 assertions replaying real #35 fixture (v1 83 injected messages -> 0); omp -p clean load v18.4.4; omp config get syncBacklog=3 immuneTurns=6 maxNotesPerUpdate=2 goal.continuationModes=[] todo.remindersMax=1; product commit a1299a6"],"next_action":"owner review + merge PR (Refs #35 #37); then live-session confirmation and receipt on #37","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0005","timestamp":"2026-09-29T21:37:56Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"be1412a8145f8b5fe3a5a128922dae1a9a1f94e845ddf33668f2542ab11e6c57","request_id":"39a82be3ff6e4209a3730e9726033bc5","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0005"} -->

Completed:
- jev-court v2 rewrite (fail-quiet, budgets, nextTurn-when-idle, stop suppression, transcript reconciliation, re-raise reuse, durable rehydrated decisions); new loop-guard (replay marking, task-echo guidance); WATCHDOG silence-first + scope disabled; config storm keys incl. syncBacklog enum-type fix; README/CURRENT/task projection updated; live ~/.omp/agent cutover with dated backup

Evidence:
- 32/32 assertions replaying real #35 fixture (v1 83 injected messages -> 0); omp -p clean load v18.4.4; omp config get syncBacklog=3 immuneTurns=6 maxNotesPerUpdate=2 goal.continuationModes=[] todo.remindersMax=1; product commit a1299a6

Decisions:
- scope advisor disabled pending hardened severity rules; court opt-in default; goal auto-continue off; upstream residue documented (async-result wake, notification-only reminder events)

Changed:
- oh-my-pi/extensions/jev-court.ts, oh-my-pi/extensions/loop-guard.ts, oh-my-pi/config/{config.yml,WATCHDOG.yml,jev-court.example.json}, oh-my-pi/README.md, tasks/TASK-ACS-0005-omp-loop-hardening.md, checkpoints/CURRENT.md

Blocked/uncertain:
- none

Next:
- owner review + merge PR (Refs #35 #37); then live-session confirmation and receipt on #37

### 2026-09-29 21:38:33 UTC — omp/qwen3.8-flash

<!-- continuity:checkpoint {"agent":"omp/qwen3.8-flash","blocked":[],"changed":["oh-my-pi/extensions/jev-court.ts, oh-my-pi/extensions/loop-guard.ts, oh-my-pi/config/{config.yml,WATCHDOG.yml,jev-court.example.json}, oh-my-pi/README.md, tasks/TASK-ACS-0005-omp-loop-hardening.md, checkpoints/CURRENT.md, .gitignore"],"completed":["jev-court v2 rewrite (fail-quiet, budgets, nextTurn-when-idle, stop suppression, transcript reconciliation, re-raise reuse, durable rehydrated decisions); new loop-guard (replay marking, task-echo guidance); WATCHDOG silence-first + scope disabled; config storm keys incl. syncBacklog enum-type fix; README/CURRENT/task projection updated; live ~/.omp/agent cutover with dated backup"],"decisions":["scope advisor disabled pending hardened severity rules; court opt-in default; goal auto-continue off; upstream residue documented (async-result wake, notification-only reminder events)"],"evidence":["32/32 assertions replaying real #35 fixture (v1 83 injected messages -> 0); omp -p clean load v18.4.4; omp config get syncBacklog=3 immuneTurns=6 maxNotesPerUpdate=2 goal.continuationModes=[] todo.remindersMax=1; product commit a1299a6"],"next_action":"owner review + merge PR (Refs #35 #37); then live-session confirmation and receipt on #37","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0005","timestamp":"2026-09-29T21:38:33Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"773fa86f649067555cc086849ce9645bfdf1afab8991efda446f55d192b467d3","request_id":"39a82be3ff6e4209a3730e9726033bc5","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0005"} -->

Completed:
- jev-court v2 rewrite (fail-quiet, budgets, nextTurn-when-idle, stop suppression, transcript reconciliation, re-raise reuse, durable rehydrated decisions); new loop-guard (replay marking, task-echo guidance); WATCHDOG silence-first + scope disabled; config storm keys incl. syncBacklog enum-type fix; README/CURRENT/task projection updated; live ~/.omp/agent cutover with dated backup

Evidence:
- 32/32 assertions replaying real #35 fixture (v1 83 injected messages -> 0); omp -p clean load v18.4.4; omp config get syncBacklog=3 immuneTurns=6 maxNotesPerUpdate=2 goal.continuationModes=[] todo.remindersMax=1; product commit a1299a6

Decisions:
- scope advisor disabled pending hardened severity rules; court opt-in default; goal auto-continue off; upstream residue documented (async-result wake, notification-only reminder events)

Changed:
- oh-my-pi/extensions/jev-court.ts, oh-my-pi/extensions/loop-guard.ts, oh-my-pi/config/{config.yml,WATCHDOG.yml,jev-court.example.json}, oh-my-pi/README.md, tasks/TASK-ACS-0005-omp-loop-hardening.md, checkpoints/CURRENT.md, .gitignore

Blocked/uncertain:
- none

Next:
- owner review + merge PR (Refs #35 #37); then live-session confirmation and receipt on #37

### 2026-09-29 21:38:59 UTC — omp/qwen3.8-flash

<!-- continuity:checkpoint {"agent":"omp/qwen3.8-flash","blocked":[],"changed":["oh-my-pi/extensions/jev-court.ts, oh-my-pi/extensions/loop-guard.ts, oh-my-pi/config/{config.yml,WATCHDOG.yml,jev-court.example.json}, oh-my-pi/README.md, tasks/TASK-ACS-0005-omp-loop-hardening.md, checkpoints/CURRENT.md, .gitignore"],"completed":["jev-court v2 rewrite (fail-quiet, budgets, nextTurn-when-idle, stop suppression, transcript reconciliation, re-raise reuse, durable rehydrated decisions); new loop-guard (replay marking, task-echo guidance); WATCHDOG silence-first + scope disabled; config storm keys incl. syncBacklog enum-type fix; README/CURRENT/task projection updated; live ~/.omp/agent cutover with dated backup"],"decisions":["scope advisor disabled pending hardened severity rules; court opt-in default; goal auto-continue off; upstream residue documented (async-result wake, notification-only reminder events)"],"evidence":["32/32 assertions replaying real #35 fixture (v1 83 injected messages -> 0); omp -p clean load v18.4.4; omp config get syncBacklog=3 immuneTurns=6 maxNotesPerUpdate=2 goal.continuationModes=[] todo.remindersMax=1; product commits a1299a6..HEAD"],"next_action":"open PR (Refs #35 #37); owner review + merge; then live-session confirmation and receipt on #37","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0005","timestamp":"2026-09-29T21:38:59Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"c2c90798055aa3992c57eec727d7f42a67301f34b6d106e1812ee683bcd0b512","request_id":"39a82be3ff6e4209a3730e9726033bc5","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0005"} -->

Completed:
- jev-court v2 rewrite (fail-quiet, budgets, nextTurn-when-idle, stop suppression, transcript reconciliation, re-raise reuse, durable rehydrated decisions); new loop-guard (replay marking, task-echo guidance); WATCHDOG silence-first + scope disabled; config storm keys incl. syncBacklog enum-type fix; README/CURRENT/task projection updated; live ~/.omp/agent cutover with dated backup

Evidence:
- 32/32 assertions replaying real #35 fixture (v1 83 injected messages -> 0); omp -p clean load v18.4.4; omp config get syncBacklog=3 immuneTurns=6 maxNotesPerUpdate=2 goal.continuationModes=[] todo.remindersMax=1; product commits a1299a6..HEAD

Decisions:
- scope advisor disabled pending hardened severity rules; court opt-in default; goal auto-continue off; upstream residue documented (async-result wake, notification-only reminder events)

Changed:
- oh-my-pi/extensions/jev-court.ts, oh-my-pi/extensions/loop-guard.ts, oh-my-pi/config/{config.yml,WATCHDOG.yml,jev-court.example.json}, oh-my-pi/README.md, tasks/TASK-ACS-0005-omp-loop-hardening.md, checkpoints/CURRENT.md, .gitignore

Blocked/uncertain:
- none

Next:
- open PR (Refs #35 #37); owner review + merge; then live-session confirmation and receipt on #37
