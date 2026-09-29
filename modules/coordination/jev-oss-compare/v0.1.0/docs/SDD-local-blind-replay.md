# SDD — Recovery routing from long-running intent and research drift

## 1. Runtime boundary

ACS-0004 is an offline shadow replay. The runner advances source events in order, invokes explicitly configured local decision models, and records recommendations. It has no hosted Jev/OpenRouter client, browser/research agent, or historic tool executor. It does not send a route to Claude or pause a live agent.

The deterministic harness owns source authority, ordering, coverage, span IDs, job DAG, evidence ledger, chronological state, and final route reduction. Laya supplies bounded semantic judgments. Model agreement never overrides provenance or user authority.

## 2. Component responsibilities

| Component | Responsibility |
| --- | --- |
| Source adapter | Read the verified raw Claude JSONL corpus; reject gold-derived, incomplete, or unauthorized sources. |
| Provenance normalizer | Emit stable ordered user, assistant, tool-call/result, research-source, delegation, and captured-compaction events with source IDs and parent links. |
| Intent ledger | Preserve attributed user-message spans, status, relations, timestamps, exact supersession edges, and stream/task context. Age alone never expires durable intent. |
| Boundary builder | Derive response, plan/proposal, research-to-plan/action, tool-action, resume, and captured-compaction checkpoints using a versioned deterministic rule set. Preserve the source event that caused each checkpoint. |
| Local decision adapter | Query one exact, local model/checkpoint at a time with a model-specific packer and typed schema. |
| Recovery reducer | Apply deterministic coverage and route policy to scored jobs and emit one shadow recommendation per covered checkpoint. |
| Receipt writer | Write private, content-free receipts containing hashes, IDs, spans, coverage, route, and timing. |

The boundary builder must not treat every assistant sentence as a formal plan. When the transcript has no structured plan event, only a reproducibly detected proposal/commitment boundary and actual tool calls can be evaluated. Unrecognized boundaries are reported as a coverage gap, not as evidence that no plan existed.

## 3. Source event envelope

A normalized event contains:

- stable event ID, stream ID, event index, and source timestamp when present;
- kind and authority (human_user, assistant_text, tool_call, tool_result, research_source, delegated_prompt, compact_boundary; human, agent, tool, or unknown);
- source file hash and line, UUID, parent UUID, sidechain/agent ID, tool-use ID, and source sequence;
- private content reference, content hash, and exact span references when atomized;
- task/context relation evidence when available, without inferring a new task ID from timestamps alone.

Raw text stays in private local input storage and never enters committed receipts. Tool-result blocks and delegated agent prompts do not become human intent. Identical duplicate UUIDs collapse with all source locations retained; conflicting content fails the source build. Unresolved parent links make affected coverage incomplete.

## 4. Event order and no-lookahead

Replay each causal conversation/sidechain forward in source order. File/array sequence is primary; timestamps are evidence, not a global merge key. A decision sees only events preceding its checkpoint. The tool result is added after the tool-call checkpoint. Future assistant explanations, research results, corrections, compacted summaries, or labels cannot repair earlier decisions.

A child stream receives the exact parent intent/evidence snapshot that existed at delegation time. If source order or parent causality is ambiguous, mark the affected segment order_unknown and do not claim complete coverage.

## 5. Decision jobs

### 5.1 User intent and relations

Classify attributed human excerpts as durable assertion, tentative/reconsidering, question-only, context-only, or unclear. Compare each eligible human message with every earlier eligible human message in its stream using stable overlapping spans. Preserve every parent pair ID, span pair, and result.

A relation edge may be unrelated, same topic, question/reopens, adds a constraint, supports, exact supersession, conflict, or unclear. Supersession targets exact prior intent spans; it never deletes source history. A partial correction cannot deactivate unrelated clauses. Unknown task context or mixed span judgments remain uncertain/incomplete.

Questions and context do not become hard tool restrictions. Durable constraints remain active until explicit exact supersession or a clear task boundary; a delay of ten hours by itself changes no status.

### 5.2 Assistant acknowledgment

For each durable/consequential user message and each explicit repeat-back request, compare the next assistant response with the user’s exact intent spans. Choose:

- accurate: the response carries forward the relevant request and constraints;
- partial: it omits or weakens at least one consequential constraint;
- omitted: it does not acknowledge or represent the instruction;
- contradicted: it restates the instruction incorrectly;
- unclear: the response/message is incomplete or the relation cannot be judged.

Use only the next assistant response available at that point. Later paraphrases do not repair an earlier miss. Keep the acknowledged user spans and response spans separate.

The versioned adapter first classifies whether acknowledgment is required for each user span. It then pairs each required span with every token-bounded text chunk from only the next assistant message, preserving both source spans and timestamps. If there is no next assistant text before the next user turn, write a deterministic omitted receipt and recommend reconfirm_intent without asking Laya to infer a missing response. Unclear intent/expectation or missing decision jobs route to escalate. For a multi-chunk response, the reducer evaluates coverage across all chunks; any missing job prevents proceed, and contradictory chunk judgments require reconfirmation.

### 5.3 Plan, claim, and action conflict

An assistant plan or commitment is an agent proposal, not user intent. Compare each eligible consequential proposal and each structured tool action with the active attributed intent spans. Tool-call input is the observed action boundary; assistant prose is not misreported as an executed action.

The model returns consistent, conflict, or uncertain, with exact proposal/action span and user-intent span IDs. A durable conflict recommends rethink_plan; uncertainty or incomplete intent coverage recommends reconfirm_intent or escalate. A proposed plan can be flagged before execution; a later tool action is checked again because an accurate plan acknowledgment does not guarantee compliant action.

### 5.4 Research evidence and transition

Create research claims from attributed assistant claim spans before an eligible plan/action boundary. The evidence ledger contains only earlier retrieved material, with source identity (URL or repository/path), version/as-of date when present, retrieval event/time, excerpt span/hash, source type, and claim-support relation.

A source request, search query, citation text without retrieved content, or agent statement is not supporting evidence. For each claim/source pair the model returns supports, contradicts, relevant_but_incomplete, irrelevant, or insufficient. No universal source-count threshold is used. Missing, stale, unversioned, indirect, contradictory, or unrepresentable evidence cannot yield proceed.

When evidence is missing, the route identifies the specific claim and missing warrant. research_more asks for more relevant evidence; dispatch_verifier recommends a bounded independent check with a named claim and source class. In this replay neither route launches a search or agent.

### 5.5 Tool and compaction checks

For each consequential tool call, apply deterministic hard-deny rules first, then compare the proposal against every active durable and relevant tentative user-intent span. Coverage lists all active candidates. A missing/capped candidate makes the checkpoint incomplete and cannot yield proceed. Unrelated safe work may continue while the affected action is held.

Run compaction evaluation only on source-captured boundaries. Current source records expose retained IDs but not compacted summary prose; semantic preservation is therefore unknown unless both pre- and post-boundary text are actually present. Never infer semantic loss from token counts alone.

## 6. Recovery route contract

Route enum: reconfirm_intent, rethink_plan, research_more, dispatch_verifier, escalate, proceed.

Each route receipt includes:

- checkpoint ID/kind, source event IDs, event order, source timestamp, and decision receipt time;
- user intent span IDs, response/proposal/action span IDs, claim IDs, as-of source/evidence IDs and hashes;
- job coverage, truncation/incompleteness reasons, model/checkpoint/config identity, raw choice/confidence semantics, and deterministic aggregation;
- route, reason code, and a bounded next-check description with no raw transcript text.

Route policy is deterministic: unresolved or incomplete coverage cannot silently become proceed; a direct durable intent conflict recommends rethink_plan; omitted/partial explicit acknowledgment recommends reconfirm_intent; no matched as-of source recommends dispatch_verifier; incomplete or contradictory source coverage recommends escalate or research_more; only covered, non-conflicting, adequately supported checkpoints may recommend proceed. No single uncertain checkpoint globally blocks unrelated work.

The route is a shadow recommendation. It is not user-facing, it does not change a historical action, and it does not prove that an agent would have accepted it.

## 7. DAG and reducer

Phase 1 fans out independent user-message status/acknowledgment-expectation and prior-user pair jobs. Phase 2 fans out next-response span checks, tool-action-to-intent, and claim-to-as-of-source jobs using the snapshots available at each checkpoint. A deterministic chronological reducer applies exact relations, computes coverage, and emits route receipts. Worker count changes throughput only; it never removes required source/pair/job coverage.

All planned jobs must end with a result, explicit abstention, or recorded failure. A cap, timeout, unscored pair, mixed span result, or queue loss is visible and makes only the affected checkpoint incomplete. Cache keys include source/checkpoint/span IDs, full request hash, profile/checkpoint revision, and runtime settings.

## 8. Lane policy

Use the frozen Laya typed-decisions profile as the primary local lane. Keep OpenJev or Kev only for a concrete comparison that can test a distinct miss hypothesis and only if comparable source/job coverage is achievable. A secondary lane is not a completion gate. Compare distinct, independently reviewed findings and latency; agreement is not a vote for correctness. Never share raw state, outputs, confidence thresholds, or cached decisions across lanes.

Do not infer common calibration from model confidence fields. Preserve each backend’s raw option scores and confidence definitions. Verify exact checkpoint and runtime identity before any call. Public/cloud endpoints and implicit fallbacks fail closed.

## 9. Failure and coverage handling

Timeouts, model mismatch, malformed answers, hidden truncation, source gaps, unknown boundaries, unresolved causality, and missing evidence are per-checkpoint failures. Record an incomplete/escalated or targeted research route and continue only where causally independent. No model, host, or endpoint fallback is permitted. Never convert a failed or missing job into proceed.

## 10. Privacy

Private transcript text and model payloads stay outside GitHub and committed output. Content-free receipts may include hashes, event/span identifiers, source categories, coverage counts, route counts, latency, and incomplete reasons. Do not log source query secrets or full URLs containing credentials.

## Current implementation boundary

Adapter/profile 1.1.0 implements acknowledgment checks, recorded tool-action conflicts, and deterministic route receipts for research jobs. Synthetic tests cover these mechanics, but no model inference has run. Assistant prose-plan boundary detection and source checks triggered specifically at that boundary remain planned work; the design above must not be read as evidence that those paths exist.

## Lineage

Owning leaf issue: [#28](https://github.com/Pukujan/agent-custom-setup/issues/28), parent: none, dependencies: none. Task ACS-0004; primary writer Codex; branch task/ACS-25-dual-jev-gates. Owner clarification: [comment #5894826843](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5894826843).
