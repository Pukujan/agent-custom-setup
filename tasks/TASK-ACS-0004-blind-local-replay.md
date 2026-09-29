# TASK-ACS-0004 — Blind recovery-routing replay for long-running intent and research drift

<!-- continuity:task {"acceptance":["Replay only the complete verified raw Claude source for blind claims; reject gold-derived or incomplete streams and preserve source/authority/causal provenance","Use Laya typed-decisions as the primary low-cost lane; secondary OSS lanes are optional and retained only for a distinct, reviewed detection hypothesis","Evaluate consequential user-message acknowledgment, proposed-plan and recorded-tool conflicts, and as-of claim/source support before plan or action boundaries","Emit reconfirm_intent, rethink_plan, research_more, dispatch_verifier, escalate, or proceed recommendations with exact event/span/evidence IDs, timestamps, coverage and receipt time","Missing, truncated, unscored, contradictory, or out-of-order coverage cannot silently yield proceed","Implement and evidence M01-M28 plus generated property/fuzz invariants without seeding known transcript failures","Report holdout honestly; the prior post-inference partition is exploratory, and only unexposed whole-session inputs qualify as hidden holdout","Emit content-free receipts accounting for every planned job, route, omission, failure, model identity, timing, and source/config hash"],"depends_on":[],"goal":"Determine whether a cheap local Laya decision lane, inside a deterministic provenance-preserving replay, can surface actionable recovery opportunities for consequential user-intent and research drift in the complete raw Claude history; retain other OSS only if they add distinct value","id":"ACS-0004","issue_url":"https://github.com/Pukujan/agent-custom-setup/issues/28","next_action":"On the other PC, rerun the focused Laya adapter suite; resolve failures, then verify the local checkpoint/runtime and resource budget before a bounded synthetic trial. Do not start full transcript inference until the suite passes and the input manifest is validated.","owner":"Codex","priority":"P1","protocol_version":"0.1.0-draft","schema":"project-continuity.task.v1","status":"active","why":"The earlier gold/hosted-Jev bakeoff did not test whether a small local lane catches long-running intent loss, conflicting decisions, or unsupported research transitions and recommends a useful, auditable recovery step"}-->

- Status: active
- Owner / primary writer: Codex
- Priority: P1
- Depends on: none for design; #25 and PR #26 are related history, not verified parents or dependencies

## Human outcome

My usual workflow is to tell Claude or Codex what I want, the success criteria and constraints, then ask it to repeat its understanding so I can correct it. During a long-running task, after many tasks or context changes, the agent may miss or weakly acknowledge that message and later make a choice that violates it. The benchmark’s main goal is to see whether Laya can catch any of these consequential failures in the prewritten transcript, and whether the same checks could help future work.

The failure chain to evaluate is: the next response omits or weakly carries forward an instruction; a later plan or tool action conflicts with active intent; the agent assumes something is impossible or paid after shallow research; or it decides it has researched enough and moves to a plan/action without direct, current evidence. A useful route should identify the claim and missing source and recommend more research or a bounded independent verifier. Generic allow/deny output is not success.

A cheap shadow backtest can be better than doing nothing if it exposes timely, provenance-backed recovery opportunities for human review without messaging an agent or executing historic actions. The tradeoff includes local runtime/resources, false-alert review time, and missed unalerted checkpoints. This one historical corpus is discovery evidence, not a future catch-rate claim; prior outputs have been reviewed and no unexposed whole-session holdout is verified. Keep the known Fish incident out of tuning and inspect it only after the frozen run. Require new unexposed sessions or prospective evaluation before claiming generalization.

## Scope and boundaries

- In scope: complete verified raw Claude replay; event/authority/causal provenance; Laya-first typed decisions; acknowledgment, plan/action intent conflict, as-of research evidence, and recovery-route recommendations; exhaustive user-message pair coverage for the offline benchmark; deterministic chronological reducer; span-level receipts; metamorphic and generated fuzz cases; truthful holdout status; optional OSS comparators with a distinct marginal-detection hypothesis.
- Out of scope: production hook/controller implementation, live agent messages, executing historic tools or research, hosted Jev/OpenRouter, known-incident prompts/rules/fixtures, gold-scored accuracy, requiring OpenJev/Kev completion, and claiming semantic compaction preservation when source prose is absent.
- Routes: reconfirm_intent, rethink_plan, research_more, dispatch_verifier, escalate, proceed. During replay these remain shadow recommendations; the system does not perform them.
- Durable intent does not expire from age alone. Preserve timestamps, task/sidechain scope, and exact supersession. If context or coverage is uncertain, do not silently proceed.
- Candidate roster: Laya typed-decisions is primary. OpenJev/Kev are optional only when they address a distinct missed-case or performance question with comparable inputs; unavailable or non-contributing lanes do not block completion.
- Full raw ACS/Grok is unavailable/unverified. Gold-derived ACS artifacts remain excluded from blind evidence.

## Observed evidence

- Live owning issue #28 is OPEN and now titled “Blind replay for long-running intent and research recovery”; the owner correction is recorded in [comment #5894826843](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5894826843).
- The local Claude source inventory is 81 raw JSONL files (14 root, 67 nested), 18,350 normalized events across 80 streams, 198 eligible human messages, and 41 captured compact-boundary records. Raw ACS/Grok is unverified.
- The new Laya typed-decision adapter/profile 1.2.0 adds acknowledgment checks, assistant prose-boundary classification, plan-to-intent checks, and deterministic shadow routes for acknowledgment, plans, recorded tool conflicts, and research evidence. The synthetic suite is green 13/13 (incl. a mutation-proven worker-pool regression test), and the pinned model scored a cold 7/7 synthetic smoke on a local CPU host (receipt `modules/coordination/jev-oss-compare/v0.1.0/reports/runs/laya-local-20260929T184900Z.json`). No full-corpus run has occurred: `inspect`/`run` reject the capped harvest with `source_must_be_the_verified_81_file_corpus`.
- The prior replay receipt corpus has partial/conflicting Laya/OpenJev/Kev results; none is terminal completion evidence. Windows OpenJev inference remains stopped. The previous session partition occurred after inference and is exploratory.
- Repository production gate modules remain optional drafts. Their current mocks do not implement or prove a general live recovery controller.
- The current M01-M14 report status is unverified and hidden whole-session holdout is not implemented. No named known incident is to be inspected until post-run audit.

## Deliverables

- Outcome-aligned PDD, SDD, benchmark protocol, and TDD under modules/coordination/jev-oss-compare/v0.1.0/docs/.
- A versioned Laya-first typed-decision profile/runner and deterministic source/replay machinery that can represent response acknowledgment, plan/action conflict, as-of evidence support, and routes.
- Synthetic metamorphic/property-fuzz coverage for provenance, chronology, exact supersession, route sensitivity, no-lookahead, and incomplete-input abstention.
- The focused Laya adapter suite has 13 synthetic cases and is green (2026-09-29, this branch). The full M01-M28 suite and generated fuzz remain unverified.
- Private replay inputs/receipts remain outside version control. Commit only code, schemas, hashes, and content-free aggregate receipts suitable for review.
- Report the raw source boundary and old partial/contradictory model receipts separately. Do not present a Claude-only result as dual-stream or as human-gold accuracy.

## Acceptance and evaluation policy

- Freeze generic prompts, decision questions, source rules, reducer, profile, and model/runtime identity before full inference. Do not seed known transcript wording or expected outcomes.
- The complete corpus replay is discovery evidence. A hidden holdout claim requires a genuinely unexposed whole root/session and descendants selected before inference; the previous post-inference split cannot be relabeled. If none exists, mark holdout not_run and use a future fresh transcript for generalization.
- Preserve exhaustive same-stream prior-user-message comparisons and exact coverage in this offline benchmark. Chunking and worker count may change throughput, not required coverage.
- Test acknowledgment only against the next response; test later plan/action boundaries again even if the response was accurate. Treat agent plans as proposals and actual tool calls as separate observed actions.
- Test source provenance as-of each claim; a search request, citation-only text, agent assertion, stale/wrong-version source, or absent excerpt is not direct support. No universal source-count minimum.
- Implement M01-M28 and generated property/fuzz checks using synthetic data; they test mechanics and directional sensitivity, not transcript correctness.
- Review the known incident only after the blind replay. Separately review a blinded sample of routed and unrouted consequential checkpoints to report observed usefulness and false-alarm/miss examples. A sample is not full gold.
- Report routes, source coverage, incomplete jobs, abstention, lane identity, latency/resource cost, and reviewed examples separately. Agreement and confidence do not establish correctness.
- Keep optional OSS lanes only if they produce distinct, independently reviewable detections at justifiable cost.

## Prior task-context proposal

The user’s task-context, message-relation, and pin-state proposal is recorded in [issue #28 comment #5874824862](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5874824862). This recovery-routing correction adds response, plan/action, evidence, and route outcomes while retaining the exhaustive same-stream message-pair coverage requirement for this offline benchmark.

## Lineage and execution identity

- Leaf owning issue: [#28](https://github.com/Pukujan/agent-custom-setup/issues/28)
- Parent ancestry: none; dependencies: none
- Primary writer: Codex
- Branch: task/ACS-0004-laya-benchmark (continuation; prior PR #26 branch `task/ACS-25-dual-jev-gates` merged)
- Source issue revision: #28 body and owner correction comment #5894826843 read 2026-09-29
- PR/CI/receipt: PR #26 MERGED 2026-09-29T18:19:06Z as `69a34dd` (verified live this session). Continuation branch `task/ACS-0004-laya-benchmark` cut from that main head carries commit `947e8a5` + continuity checkpoint; a new PR (Refs #28, never a closing keyword) with fresh checks is required — this is not a delivery claim.

## Checkpoint log

### 2026-09-28 — scope corrected and provenance audited

- Completed: verified live #28; documented owner direction to replace the gold/peer bakeoff with blind local-model replay; recorded that Jev/OpenRouter are forbidden for this run; confirmed model/device inventory without inference.
- Evidence: #28 comments above; `acs_20h_export_meta.json`; `claude_full_export_meta.json`; local Ollama `/api/tags`; `nvidia-smi`; read-only audits from transcript/backend reviewers.
- Decision: do not infer or label ACS/Grok raw coverage from the gold-derived fallback; exclude it until a clean source exists. Re-export Claude from raw JSONL, preserving root/sidechain causality and compact boundaries.
- Changed: issue #28 comments only so far; no source code or model services changed.
- Blocker: MacBook Pro model runtime/endpoint and actual ACS/Grok transcript are unverified/unavailable from this checkout.
- Next atomic action: inspect raw Claude schema and implement a provenance-preserving source adapter plus typed local backend smoke checks; keep inference disabled until endpoints are confirmed.
- Decisions: the original checkpoint's decision remains recorded above: exclude curated ACS/Grok fixtures and preserve Claude source provenance.
- Blocked/uncertain: the original checkpoint's blocker remains recorded above: the Mac endpoint and clean ACS/Grok source had not yet been verified.
- Next: inspect raw Claude schema and implement a provenance-preserving source adapter plus typed local backend smoke checks.

### 2026-09-28 — live baseline resumed on Gravebuster

- Completed: revalidated the live issue and source protocol; verified the Gravebuster replay process over Tailscale. The 9B baseline is still live with a content-free receipt advancing (1,655 rows observed at 16:19 UTC). The Windows OpenJev 4B lane was stopped at the user's request due to PC load and will not be restarted; its 11,557-row receipt is partial and not a completed lane.
- Evidence: issue #28 correction/progress receipt [#5874138365](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5874138365); Gravebuster process PID 2944874, elapsed 1:41:56 at 16:19 UTC; source manifest verifies 81 raw Claude JSONL files; 64 offline unit tests pass. The model endpoint for this active run is the verified Mac-hosted APUS OpenJev 9B reached through the Gravebuster tunnel; the Windows PC is not serving inference.
- Limits: Claude-only; raw ACS/Grok input is unavailable and curated ACS fixtures remain excluded. The 4B lane is incomplete. The session partition was created after inference began and remains exploratory, not a preregistered hidden holdout. OpenJev scores are uncalibrated and do not measure correctness.
- Decision: preserve the active 9B run, then run the staged context-compaction adapter and auto-mode adapter separately on Gravebuster. The auto-mode lane remains tool-only; native compaction is not user-pin/research coverage.
- Changed: corrected stale run status in live issue comment #5874138365; no inference was restarted on Windows.
- Next atomic action: allow the active baseline to reach terminal status, then verify its final receipt and run summary before starting either adapter.
- Decisions: preserve the 4B receipt as partial, keep the user-stopped Windows inference off, and run adapters only after the 9B baseline.
- Blocked/uncertain: the baseline was reported live at 16:19 UTC in this checkpoint; the later handoff entry below corrects that observation and records the terminal transport loss.
- Next: wait for terminal baseline status, verify the receipt and summary, then run adapters sequentially.

### 2026-09-28 — benchmark interruption and new-session handoff

- Completed: stopped relaunch attempts at the user’s request; inventoried saved private receipts; rendered the content-free HTML status report; recorded the owner’s design proposal in live issue comment #5874824862.
- Evidence: issue #28 is OPEN; local `HEAD` is `2dbcf9f65ab2e4f1dc8265dadd980c34bf59d3ae` and matches `origin/task/ACS-25-dual-jev-gates`; 9B Gravebuster receipt has 4,180 rows (local copy 3,795); 4B has 11,557 local rows versus 4,429 in the Gravebuster copy. The 4B/9B copies conflict and neither lane has a terminal summary. Laya receipts: 2,134 rows (2,114 incomplete) and a separate 1,221-row run (1,057 scored, 126 incomplete). Kev 0.8B: 150 rows (80 scored, 68 incomplete). Compaction and auto-mode have plans only and no inference receipts.
- Report: `reports/blind-local-replay.html` uses content-free receipts only. Its model-identity display was corrected to use the explicit `laya-typed-decisions` and `kev-0.8b` lane IDs when upstream `model_id` is generic. The report is a partial status artifact; it does not establish accuracy or completed runs.
- Limits: no current model runner is live; Windows inference remains stopped. Raw ACS/Grok is unavailable, the post-inference partition is exploratory, and the local changes/report are not yet committed or pushed. No human-gold claim is supported.
- Decision: preserve the conflicting receipts and report both; do not restart Windows. Continue from this handoff in a new session, keeping baseline, compaction, and auto-mode experiments separate.
- Next atomic action: commit product/docs and synchronize with `continuity checkpoint ACS-0004`; then resume the requested Gravebuster baseline and run the two adapters sequentially, refreshing the HTML from final receipts.
- Decisions: treat all row counts as partial receipts, preserve disagreement between copies, and keep the design proposal separate from benchmark acceptance.
- Blocked/uncertain: no terminal summaries exist for the current lanes; the model identity in old Laya/Kev receipts comes from explicit lane IDs because their `model_id` fields are generic.
- Next: commit product/docs, run the continuity checkpoint push, then continue the baseline and adapters in the next session.

### 2026-09-28 17:14:02 UTC — Codex

<!-- continuity:checkpoint {"agent":"Codex","blocked":["No baseline or adapter runner is active; 4B/9B terminal summaries are missing; PR #26 is behind main and current-base checks are pending."],"changed":["modules/coordination/jev-oss-compare/v0.1.0/, tasks/TASK-ACS-0004-blind-local-replay.md, checkpoints/CURRENT.md"],"completed":["Committed the replay harness, design/test/report specifications, content-free partial HTML, current task projection, and benchmark status handoff."],"decisions":["Preserve incomplete and conflicting receipts; keep task-context design proposal separate from current exhaustive ACS-0004 acceptance; do not restart Windows inference."],"evidence":["Commit d46f4e1 on task/ACS-25-dual-jev-gates; issue #28 comment https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5874824862; continuity validate reports VALID with an existing issue-log-format marker warning; receipts remain partial and conflicting as recorded in task ACS-0004."],"next_action":"Continue the Gravebuster baseline from saved cache, then run fast-jev-compaction and auto-mode sequentially and refresh the content-free HTML report.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0004","timestamp":"2026-09-28T17:14:02Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"317510008f7b16101006ba0655fb150539033845adf12742fd17b1259e466f3a","request_id":"d439c0ea83cf4701808f5a07c97f547f","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0004"} -->

Completed:
- Committed the replay harness, design/test/report specifications, content-free partial HTML, current task projection, and benchmark status handoff.

Evidence:
- Commit d46f4e1 on task/ACS-25-dual-jev-gates; issue #28 comment https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5874824862; continuity validate reports VALID with an existing issue-log-format marker warning; receipts remain partial and conflicting as recorded in task ACS-0004.

Decisions:
- Preserve incomplete and conflicting receipts; keep task-context design proposal separate from current exhaustive ACS-0004 acceptance; do not restart Windows inference.

Changed:
- modules/coordination/jev-oss-compare/v0.1.0/, tasks/TASK-ACS-0004-blind-local-replay.md, checkpoints/CURRENT.md

Blocked/uncertain:
- No baseline or adapter runner is active; 4B/9B terminal summaries are missing; PR #26 is behind main and current-base checks are pending.

Next:
- Continue the Gravebuster baseline from saved cache, then run fast-jev-compaction and auto-mode sequentially and refresh the content-free HTML report.

### 2026-09-29 — recovery goal and setup audit

Completed:
- Verified the live owning issue; appended the owner’s near-verbatim problem sequence and updated issue #28 title/body to make useful recovery from consequential intent/research drift the benchmark goal.
- Audited the Laya DAG, current optional gate modules, PDD/SDD/TDD, metamorphic protocol and holdout status with repository evidence and a read-only gpt-6-sol review.
- Updated the local PDD, SDD, TDD, benchmark protocol, task and CURRENT projections.

Evidence:
- [Issue comment #5894826843](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5894826843).
- The current Laya adapter/profile covers pin status, user-message relations, tool-versus-pin checks and claim/source pairs; it lacks next-response acknowledgment and recovery-route output.
- The report marks M01-M14 unverified and hidden holdout not implemented. The earlier post-inference split is exploratory.
- Existing production gate modules are optional drafts; their current mocks do not establish an end-to-end recovery flow.
- No new Laya full-corpus inference or benchmark tests were run.

Decisions:
- Laya is the primary cheap candidate; OpenJev/Kev are optional comparators only if they test a distinct miss hypothesis.
- Treat the full historical replay as exploratory unless an unexposed whole-session holdout is proven.
- Keep live recovery-controller implementation separate from ACS-0004.

Changed:
- Issue #28 title/body/comment; local PDD, SDD, TDD, benchmark protocol, task and CURRENT projections.

Blocked/uncertain:
- The Laya adapter does not yet implement acknowledgment or recovery routes.
- New synthetic metamorphic/fuzz cases are specified but not implemented or evidenced.
- A valid hidden holdout is unavailable; no Gravebuster full-corpus resource run has started.

Next:
- Rerun the focused synthetic suite after the fixture correction, fix any remaining failures, and synchronize the evidence docs before a bounded local resource trial.

### 2026-09-29 — owner goal and acknowledgment-route update

Completed:
- Recorded the owner’s failure sequence and the backtest-versus-no-op tradeoff in the live issue body/comment and aligned the PDD, benchmark protocol, SDD, TDD, task, and CURRENT projection. Added Laya adapter/profile 1.1.0 acknowledgment expectation, next-assistant-response span jobs, deterministic omission/route aggregates, tool/research route output, and a rule that only retrieved source content can support claims.

Evidence:
- Issue #28 comments [#5895286616](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5895286616) and [#5895676182](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5895676182); focused pytest result: 9 passed; Python compilation and profile JSON parsing passed; git diff --check passed; continuity validate reports VALID with the existing stale issue-log-format marker warning.

Decisions:
- The replay-versus-no-op value remains a hypothesis. Treat this historical corpus as discovery only; no catch-rate/generalization claim. Do not inspect the named incident before the frozen replay.

Changed:
- Issue #28 body/comments; profiles/laya-typed-decisions/v1/profile.json; scripts/laya_typed_decisions/v1/runner.py; new tests/test_laya_typed_decisions_v1.py; PDD/SDD/TDD/benchmark protocol/task/CURRENT.

Blocked/uncertain:
- No Laya model inference or full-corpus replay has run; no untouched whole-session holdout is verified; assistant prose-plan boundary detection, M01-M28 completion, and generated fuzz remain outstanding. The new tests validate mechanics, not Laya semantic quality.

Next:
- Add assistant prose-plan boundary detection and attach as-of evidence/recovery routes to that checkpoint; add synthetic miss checks before freezing the adapter for a bounded local resource trial.

### 2026-09-29 — assistant boundary path added, verification pending

Completed:
- Extended adapter/profile to classify assistant spans as proposed plans, factual claims, both, other, or unclear; created plan-to-active-intent jobs; moved research checks to Laya-classified factual-claim checkpoints and rechecked classified claims at coding action boundaries. Added synthetic tests for boundary job creation, plan-conflict routing, and current-task claim selection.

Evidence:
- The last focused pytest run reported 11 passed and one failed because the no-evidence fixture omitted a claim count; the fixture was corrected afterward, but the suite has not been rerun. Python compilation passed before these latest assistant-boundary edits. No model process or transcript inference was started.

Decisions:
- Treat the expanded adapter as unverified until the focused suite passes. No hosted or historic tool calls; the known incident remains uninspected.

Changed:
- Laya profile/runner, focused Laya tests, and the task/current projection. These changes were local and uncommitted at this checkpoint; the live issue progress comment still needed reconciliation.

Blocked/uncertain:
- The expanded runner may still have integration issues; full M01-M28/fuzz validation and Laya semantic quality remain unverified.

Next:
- Rerun tests/test_laya_typed_decisions_v1.py, fix any remaining failures, and reconcile the live issue/evidence documents before a bounded synthetic resource trial.

### 2026-09-29 18:18:07 UTC — Codex

<!-- continuity:checkpoint {"agent":"Codex","blocked":["Focused synthetic suite not rerun after fixture correction; full M01-M28/property fuzz and Laya inference remain unverified; fresh PR checks after pushing are pending."],"changed":["modules/coordination/jev-oss-compare/v0.1.0/{docs,profiles/laya-typed-decisions/v1,scripts/laya_typed_decisions/v1,tests/test_laya_typed_decisions_v1.py,scripts/replay_sources.py}; tasks/TASK-ACS-0004-blind-local-replay.md; checkpoints/CURRENT.md"],"completed":["Committed and pushed the Laya 1.2.0 typed-decision profile/runner, worker, focused synthetic suite, updated PDD/SDD/TDD/protocol, and corrected task/CURRENT handoff projections; recorded the owner problem sequence and discovery-only evaluation boundary."],"decisions":["Keep issue #28 open and the adapter explicitly unverified until the focused suite passes; keep the historical corpus discovery-only, do not inspect the named incident before a frozen run, and make no accuracy/generalization or completion claim."],"evidence":["GitHub branch task/ACS-25-dual-jev-gates received product commit e084ab0; continuity validate is VALID with the existing stale issue-log-format marker warning; last focused suite run was 11 passed/1 fixture mismatch and the fixture was patched afterward but not rerun; no Laya inference or full-corpus replay was started; PR #26 was OPEN with auto-merge enabled and its old head checks are stale pending a fresh run."],"next_action":"On the other PC, pull task/ACS-25-dual-jev-gates; rerun tests/test_laya_typed_decisions_v1.py and fix any failures; then verify the local Laya runtime/checkpoint and available Gravebuster resources, run a bounded synthetic resource trial, and validate the frozen source manifest before any transcript replay.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0004","timestamp":"2026-09-29T18:18:07Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"eea324240bcd57976866737de9c9da579904626d23f5173e9bc8b0d09986ba7a","request_id":"acs0004-handoff-e084ab0-20260929","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0004"} -->

Completed:
- Committed and pushed the Laya 1.2.0 typed-decision profile/runner, worker, focused synthetic suite, updated PDD/SDD/TDD/protocol, and corrected task/CURRENT handoff projections; recorded the owner problem sequence and discovery-only evaluation boundary.

Evidence:
- GitHub branch task/ACS-25-dual-jev-gates received product commit e084ab0; continuity validate is VALID with the existing stale issue-log-format marker warning; last focused suite run was 11 passed/1 fixture mismatch and the fixture was patched afterward but not rerun; no Laya inference or full-corpus replay was started; PR #26 was OPEN with auto-merge enabled and its old head checks are stale pending a fresh run.

Decisions:
- Keep issue #28 open and the adapter explicitly unverified until the focused suite passes; keep the historical corpus discovery-only, do not inspect the named incident before a frozen run, and make no accuracy/generalization or completion claim.

Changed:
- modules/coordination/jev-oss-compare/v0.1.0/{docs,profiles/laya-typed-decisions/v1,scripts/laya_typed_decisions/v1,tests/test_laya_typed_decisions_v1.py,scripts/replay_sources.py}; tasks/TASK-ACS-0004-blind-local-replay.md; checkpoints/CURRENT.md

Blocked/uncertain:
- Focused synthetic suite not rerun after fixture correction; full M01-M28/property fuzz and Laya inference remain unverified; fresh PR checks after pushing are pending.

Next:
- On the other PC, pull task/ACS-25-dual-jev-gates; rerun tests/test_laya_typed_decisions_v1.py and fix any failures; then verify the local Laya runtime/checkpoint and available Gravebuster resources, run a bounded synthetic resource trial, and validate the frozen source manifest before any transcript replay.

### 2026-09-29 — Laya local runtime proven; full replay blocked on corpus-host access

- Completed: on this device (Apple-Silicon CPU host), installed the pinned SDK (laya 0.3.20 @git 23a17522aa4942da6cce53a995a275760320b691), staged the pinned HF snapshot @1a793eb568e6718f15941d08f85432581df534e3, and ran the pinned-model cold synthetic smoke: 7/7 jobs scored, 2 workers, batch latency 342–1125 ms. Fixed two production bugs found at runtime: `_OutputCache` chmod now only touches directories it creates; `_WorkerPool.infer` carries `enqueued_monotonic` into the inflight record. Added an in-process mutation-proven regression test for the pool path (drop-enqueue → `worker_batch_timeout`; drop-stamp → `KeyError`); suite 13/13. Demonstrated the corpus guard: `inspect` and `run` reject the capped harvest with `source_must_be_the_verified_81_file_corpus`.
- Evidence: content-free receipt `modules/coordination/jev-oss-compare/v0.1.0/reports/runs/laya-local-20260929T184900Z.json`; unittest output 13/13 OK; guard rejection JSON for run-id `laya-probe-20260929`. PR #26 (old branch) MERGED at 2026-09-29T18:19:06Z into main @69a34dd; this continuation lives on new branch `task/ACS-0004-laya-benchmark` cut from that main head.
- Decisions: mechanics-only — no catch-rate/backtest claim; `queue_wait_ms` documented as enqueue→result latency; capped harvest treated as non-evidence; old receipt fingerprints change with the runner fix (expected, versioned on-branch).
- Changed: runner.py (2 fixes), tests/test_laya_typed_decisions_v1.py (regression test), reports/runs/laya-local-20260929T184900Z.json, docs/REPORT-local-blind-replay.md (status section), docs/PDD-local-blind-replay.md:38 (1.2.0/boundary-gate/smoke corrections), .gitignore (`.venv-laya/`, `.laya-tmp/`), task + CURRENT projections.
- Blocked/uncertain: full 81-file replay unreachable from this device — Gravebuster SSH permission denied; Cortex tailnet node reachable but SSH/22 closed and its Ollama cannot serve a ModernBERT classifier. Base-English Laya sidecar (:8770 on Gravebuster) exposes no typed-decisions contract.
- Next: obtain corpus-host access (Gravebuster key or Cortex SSH), run the full raw Claude DAG replay from this branch on that host, then refresh the HTML report from terminal receipts.

### 2026-09-29 19:15:06 UTC — omp

<!-- continuity:checkpoint {"agent":"omp","blocked":["full 81-file replay needs corpus-host access: Gravebuster SSH denied from this device; Cortex SSH closed"],"changed":["modules/coordination/jev-oss-compare/v0.1.0/{scripts/laya_typed_decisions/v1/runner.py,tests/test_laya_typed_decisions_v1.py,reports/runs/laya-local-20260929T184900Z.json,docs/REPORT-local-blind-replay.md,docs/PDD-local-blind-replay.md}; .gitignore; tasks/TASK-ACS-0004-blind-local-replay.md; checkpoints/CURRENT.md"],"completed":["Pinned Laya runtime proven locally: cold synthetic smoke 7/7 (SDK 0.3.20 @23a17522, model @1a793eb5); pool enqueue-stamp + cache chmod fixes with mutation-proven regression test; suite 13/13; corpus guard rejection demonstrated on capped harvest; content-free receipt committed."],"decisions":["mechanics-only claim boundary; queue_wait_ms documented as enqueue-to-result latency; new branch task/ACS-0004-laya-benchmark continues merged ACS-0004 scope"],"evidence":["reports/runs/laya-local-20260929T184900Z.json; unittest 13/13 OK; inspect/run reject with source_must_be_the_verified_81_file_corpus; PR #26 verified MERGED as 69a34dd (live gh api)"],"next_action":"open PR (Refs #28) for task/ACS-0004-laya-benchmark, publish #28 receipt comment, then run full DAG replay once corpus-host access is granted","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0004","timestamp":"2026-09-29T19:15:06Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"557da70392aa958e184ed22ef621aee265d26add44511c3af5ac7a72f667f3d3","request_id":"c967c27d353948fb912ed63ef33177ae","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0004"} -->

Completed:
- Pinned Laya runtime proven locally: cold synthetic smoke 7/7 (SDK 0.3.20 @23a17522, model @1a793eb5); pool enqueue-stamp + cache chmod fixes with mutation-proven regression test; suite 13/13; corpus guard rejection demonstrated on capped harvest; content-free receipt committed.

Evidence:
- reports/runs/laya-local-20260929T184900Z.json; unittest 13/13 OK; inspect/run reject with source_must_be_the_verified_81_file_corpus; PR #26 verified MERGED as 69a34dd (live gh api)

Decisions:
- mechanics-only claim boundary; queue_wait_ms documented as enqueue-to-result latency; new branch task/ACS-0004-laya-benchmark continues merged ACS-0004 scope

Changed:
- modules/coordination/jev-oss-compare/v0.1.0/{scripts/laya_typed_decisions/v1/runner.py,tests/test_laya_typed_decisions_v1.py,reports/runs/laya-local-20260929T184900Z.json,docs/REPORT-local-blind-replay.md,docs/PDD-local-blind-replay.md}; .gitignore; tasks/TASK-ACS-0004-blind-local-replay.md; checkpoints/CURRENT.md

Blocked/uncertain:
- full 81-file replay needs corpus-host access: Gravebuster SSH denied from this device; Cortex SSH closed

Next:
- open PR (Refs #28) for task/ACS-0004-laya-benchmark, publish #28 receipt comment, then run full DAG replay once corpus-host access is granted
