# TASK-ACS-0004 — Blind local decision-model transcript replay

<!-- continuity:task {"acceptance":["No Jev/OpenRouter requests in code or replay receipts","Source normalization rejects curated/gold-derived or incomplete streams as blind evidence","Every eligible user event is related against all prior user events within its own conversation, with explicit coverage and truncation receipts","Every tool event is checked against active pins after deterministic hard-deny rules","Research and compaction gates use only evidence/snapshots available as of each event","Laya/OpenJev/Kev lanes run independently and record model/checkpoint/device/confidence semantics","Metamorphic and hidden-session holdout suites pass without encoding known transcript failures","A replay receipt records source hashes, model configs, input coverage, outputs, latency, failures, and lane divergence without leaking transcript text"],"depends_on":[],"goal":"Build a deterministic, no-gold, blind walk-forward replay across valid Claude and ACS/Grok transcript sources using local Laya, OpenJev, and Kev decision-model lanes for user-message pins, research readiness, tool gating, and captured compaction events","id":"ACS-0004","issue_url":"https://github.com/Pukujan/agent-custom-setup/issues/28","next_action":"Commit and checkpoint the current implementation/docs/report; then continue the Gravebuster baseline and run fast-jev-compaction and auto-mode adapters sequentially before rendering the final content-free HTML report.","owner":"Codex","priority":"P1","protocol_version":"0.1.0-draft","schema":"project-continuity.task.v1","status":"active","why":"Prior benchmark conclusions were contaminated by hand-curated gold, incomplete event coverage, and lane comparisons that did not test whether the judge naturally detects agents' research and instruction failures"}-->

- Status: active
- Owner / primary writer: Codex
- Priority: P1
- Depends on: none for design; source history in #25/#26 is related context, not a parent dependency

## Human outcome

Find whether small local decision models naturally surface instruction drift, weak research, unsafe tool calls, loss of user intent during compaction, and reconsideration across Claude Code and ACS/Grok histories—without teaching the benchmark which known mistakes to find.

## Scope and boundaries

- In scope: deterministic forward-only transcript replay; independent model lanes; user-message relation/pin state; research-evidence readiness; hard-deny plus pinned-message tool checks; captured before/after compaction checks; event-level receipts; metamorphic tests; session-level hidden holdout; local model comparison up through 9B.
- Out of scope: Jev, OpenRouter, external inference, human-gold scoring, curated error seeds, peer OSS bakeoff, replaying tools against the filesystem/network, changing production gates, or treating lane agreement as correctness.
- Candidate roster: Laya; OpenJev 4B on this Windows PC; OpenJev 9B on the MacBook Pro if the user meant the APUS 9B family; Kev 0.8B/4B/9B where actually hosted. Preserve exact upstream IDs/revisions and quantization. Do not silently count a 26B-total/4B-active routed model as 4B.
- Model calls are disabled until a health/model-list request confirms the exact local endpoint and checkpoint. No Jev/OpenRouter fallback is permitted.
- State/context packing is model-specific. Compare every historical user message exhaustively in deterministic chunks/pairs where necessary; never silently drop history to fit a model. Record complete pair coverage, content hashes, and any source text that cannot be represented. Tool checks use only currently active pin candidates and preserve pin provenance. Research uses only evidence present before that event. Compaction applies only to source-captured boundaries with pre/post context evidence.
- Each conversation/root agent and each sidechain is a separate stream unless parent-child causality is explicitly reconstructed. Never merge unrelated sessions merely by timestamp. Exclude curated ACS/Grok fallback data from blind claims.

## Observed starting evidence

- Repository revision: `2dbcf9f65ab2e4f1dc8265dadd980c34bf59d3ae` on `task/ACS-25-dual-jev-gates`; working tree clean at start.
- Issue #28 was still titled and scoped as a gold-scored multi-lane bakeoff. Owner correction was recorded at [comment #5867443649](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5867443649); evidence correction at [comment #5867480911](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5867480911).
- `acs_20h_export_meta.json` records `readtranscript=false`; its 70 users derive from `fixtures/acs_chat_gold/turns.json`, and its 66 tools from a shell-only fixture with null results. It is not a raw blind ACS/Grok transcript and is excluded.
- Claude export metadata lists 81 original local JSONL files (14 root, 67 nested), 388 merged user rows, 7,797 tools, duplicate IDs, and text caps (user 4,000 chars, args 500, results 800). Raw sources preserve UUID/parent/sidechain/agent provenance and 41 compact-boundary events; normalize raw sources instead of replaying the harvest.
- This PC currently has an RTX 4060 with 8GB VRAM; Ollama model inventory contains only `nomic-embed-text`. The MacBook Pro appears on the tailnet, but no usable model inventory/API was reachable during initial read-only probes. These are current observed facts, not a claim that the requested models are absent from all runtimes.
- No Jev or model inference request has been made in this task.

## Deliverables

- PDD, SDD, benchmark protocol (blind holdout, metamorphic tests, lane isolation), and TDD in `modules/coordination/jev-oss-compare/v0.1.0/docs/`.
- A backend-neutral local typed-decision API adapter and deterministic source-normalization / walk-forward runner in `modules/coordination/jev-oss-compare/v0.1.0/`.
- Private/local normalized replay inputs and output receipts must remain outside version control; commit only manifests, hashes, code, and aggregate results safe for review.
- Report source gaps separately from model failures. Until raw ACS/Grok input is recovered, Claude-only results cannot be presented as dual-stream results.

## Acceptance and evaluation policy

- No model-specific prompt, rule, or threshold is tuned against revealed transcript failures. Freeze code/config before opening the hidden session output.
- Hidden holdout is selected by whole conversation/session, not random event rows; preserve temporal order inside each held-out stream.
- Metamorphic checks cover explicit correction/supersession, tentative exploration versus durable intent, delayed reconsideration, assistant/tool text not becoming user intent, irrelevant history, event-order leakage, source-role/sidechain isolation, hard-deny invariance, and missing/truncated evidence forcing an explicit incomplete/abstain state.
- Report per-lane counts and disagreements by gate, coverage/truncation, abstention, latency, errors, and confidence distribution. These are descriptive discovery measures; none implies human-gold accuracy.
- Model-specific confidence fields and context behavior must be recorded with their definitions; do not transfer thresholds between Laya, OpenJev, and Kev.

## Task-context design proposal

The user’s task-context, message-relation, and pin-state proposal is recorded in [issue #28 comment 5874824862](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5874824862). It keeps immutable source events separate from revisable task-context annotations and append-only relations. The proposal does not change ACS-0004 acceptance: exhaustive prior-user-message comparisons remain required; retrieval may prioritize work or run as a later shadow lane, but cannot replace exhaustive coverage without a task revision.

## Lineage and execution identity

- Leaf owning issue: [#28](https://github.com/Pukujan/agent-custom-setup/issues/28)
- Parent ancestry: none declared in live issue; #25 and PR #26 are related history, not verified parents
- Primary writer: Codex
- Branch: `task/ACS-25-dual-jev-gates`
- Source issue revision: issue #28 body/comments read 2026-09-28; owner corrections appended before this projection
- PR/CI/receipt: PR #26 is OPEN on this branch with auto-merge enabled; its last `gates` check succeeded, but the PR is BEHIND `main` and does not include these unpushed ACS-0004 files. The 2026-09-28 handoff and pending gates are recorded in issue comment [#5874824862](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5874824862).

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
