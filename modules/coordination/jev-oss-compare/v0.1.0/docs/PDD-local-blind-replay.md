# PDD — Recovery routing from long-running intent and research drift

**Status:** owner-directed outcome for ACS-0004 / issue #28. This is a blind, offline replay experiment. Jev/OpenRouter inference is prohibited. Laya is the primary low-cost candidate; other OSS lanes are optional comparators.

## Human problem

My usual workflow is to tell Claude or Codex what I want, the success criteria and constraints, then ask it to repeat its understanding so I can correct it. During a long-running task, after many tasks or context changes, the agent may miss or weakly acknowledge that message and later make a choice that violates it. The benchmark’s main goal is to see whether Laya can catch any of these consequential failures in the prewritten transcript, and whether the same checks could help future work.

The failure chain I want checked is:

1. I send an instruction, including what I need and any success criteria or constraints. Claude may acknowledge it weakly or skip the repeat-back that would let me correct a misunderstanding.
2. Later, Claude makes a plan or takes an action that conflicts with that instruction.
3. Claude may decide something cannot be done or costs money after too little research, then stop exploring.
4. Claude may decide it has researched enough and move from research to a plan or action without direct, current evidence. A useful check would identify the specific unsupported claim or missing source and recommend more research or a bounded independent verifier.

The decision lane should show exactly what triggered its concern and recommend a useful next step: reconfirm intent, rethink the plan, research the claim, dispatch a verifier, escalate uncertainty, or proceed. A generic allow/deny label is not success, and uncertainty should not automatically stop unrelated safe work.

## Main goal and success breakdown

Determine whether local Laya can surface actionable recovery opportunities from the complete verified raw Claude transcript, with exact provenance and at the point they occur.

1. **Instruction acknowledgment:** compare a consequential user message with the next assistant response. Detect accurate, partial, omitted, contradicted, and unclear carry-forward. An explicit user request to repeat or confirm understanding makes this check mandatory.
2. **Intent conflict:** compare an assistant’s proposed plan or recorded tool action with active user intent. Agent prose is an agent proposal, never user authority. Durable intent does not expire by age alone; only exact supersession or an explicit task boundary changes scope.
3. **Research warrant:** before a factual, availability, cost, or capability claim advances from research to plan/action, compare the claim with sources available as of that point. Preserve source identity/version, retrieved span/hash, timestamp, and direct-support relation. No universal source-count minimum.
4. **Recovery route:** emit one of reconfirm_intent, rethink_plan, research_more, dispatch_verifier, escalate, or proceed, with the triggering event, exact spans, intent/evidence IDs, coverage status, and recommendation rationale.

The replay reports what the frozen lane would have recommended, not what a live agent would have done. It does not claim task recovery, accuracy, recall, or future catch rate without a later independent review or prospective evaluation.

## Why the backtest can be better than doing nothing

Doing nothing has no inference or review cost, but it also produces no early warning, no auditable recovery candidate, and no evidence about whether this class of safeguard can help. A local shadow replay is a bounded experiment: it can reveal whether Laya surfaces timely, source-grounded opportunities to reconfirm, reconsider, or verify before a consequential transition. It does not message an agent or execute historical actions. We will measure actual runtime/resource use and review time; false alerts still have a cost, so route volume alone is not a win.

This is a hypothesis, not an established benefit. A useful result requires reviewers to find some recommendations actionable and supported by the cited transcript evidence, while also examining unalerted checkpoints for misses. If the lane only emits generic warnings, repeats already-obvious signals, or adds more review burden than useful findings, that is evidence to revise or stop it. The available corpus is discovery data: it cannot establish general catch rate because it is one historical transcript collection, prior outputs have been inspected, and no valid hidden whole-session holdout is verified. Keep the known Fish incident out of tuning and inspect it only after the frozen run; use genuinely new sessions or prospective evaluation for any generalization claim.

## Current evidence and gaps

- The raw Claude source has 81 JSONL files, 18,350 normalized events across 80 streams, and 198 eligible human messages. Raw ACS/Grok is not verified; gold-derived ACS fixtures remain excluded.
- Laya adapter/profile 1.1.0 now adds an acknowledgment-expectation decision and span-paired checks against only the next assistant message. The deterministic reducer emits shadow routes for acknowledgment, recorded tool/intent, and research gates. Assistant prose-plan boundary detection is still unimplemented. These paths have synthetic tests but no Laya inference or full-transcript run yet.
- The existing user-message and tool/research jobs provide provenance-bearing shadow signals. They do not implement a live recovery controller.
- The live issue body and owner correction comment now state the recovery goal and backtest tradeoff; the latter remains an untested hypothesis.
- The report marks the M01–M14 suite unverified and whole-session hidden holdout not implemented. Previous post-inference partitions are exploratory and cannot be called hidden.
- Existing ACS gate modules are optional drafts. Their current mock checks do not establish this end-to-end recovery behavior.

## Hypotheses

| Hypothesis | Status | Confirming evidence | Refuting or limiting evidence |
| --- | --- | --- | --- |
| H1: Laya can identify when an explicit consequential user instruction is omitted or contradicted by the next assistant response | Untested | Provenance-backed response checks surface reviewable omissions or contradictions | Atomic chunks lose qualifiers, or labels are generic/unclear |
| H2: Laya can identify a plan/tool choice that conflicts with active intent | Untested | Conflict decisions cite the exact user intent and proposed action | Intent state is incomplete, or the model misses conflicts |
| H3: As-of evidence checks can distinguish support from unsupported agent claims | Untested | Claims link to directly supporting or contradicting prior retrieved source spans | Source capture is incomplete or evidence matching is too lossy |
| H4: A recovery route is more useful than a binary veto | Untested | Routes identify what to reconfirm, research, or verify with provenance | False alarms create noise or route recommendations are not actionable |
| H5: A small local lane can run the workload within available resources | Untested | A bounded resource trial completes with complete job accounting and measured latency/RSS | Context packing, memory pressure, or model errors make coverage incomplete |
| H6: Secondary OSS lanes add distinct value beyond Laya | Optional / untested | Blinded review finds additional consequential cases with exact evidence at acceptable cost | Lanes only agree, duplicate alerts, or fail to complete equal-coverage runs |

## Counter-signals and caveats

- A historical replay is not an intervention; it can show a recommendation that might have helped, not prove the agent would recover.
- A single Claude corpus and already-visible history can overfit. Freeze the generic profile before inference; keep the known incident out of prompts, rules, and fixture selection; inspect it only after the blind run. The corpus run is exploratory if no genuinely unexposed whole-session holdout is available.
- The current corpus has 14 root sessions and prior outputs have been reviewed. A newly selected subset from it is not automatically an untouched holdout. Use new, unexposed sessions for a later holdout claim.
- Secondary model agreement is not correctness. Keep another OSS lane only if it adds independently reviewed detections beyond Laya.
- Full exhaustive message-pair coverage is an offline benchmark requirement, not necessarily the production retrieval strategy. Atomic chunking can split qualifiers; retain span provenance and surface disagreement/incomplete coverage.

## Scope and non-goals

- **In scope:** full raw Claude replay; deterministic event order and source authority; Laya-first typed decisions; consequential response acknowledgment; plan/action versus intent; as-of source-to-claim checks; recovery-route recommendations; exact event/span/evidence receipts; synthetic metamorphic and generated robustness cases; honest holdout status; optional OSS comparator only with a distinct hypothesis.
- **Out of scope:** production enforcement or agent messaging; executing historic tools or research requests; hosted Jev/OpenRouter; curating known failure labels into the blind run; treating model agreement or route counts as accuracy; requiring OpenJev/Kev completion when they do not add value; ACS/Grok claims without a genuine raw source.

## Proposed flow

~~~mermaid
graph TD
  U[Human instruction] --> P[Attributed intent]
  P --> A[Next response check]
  P --> D[Plan and action checks]
  D --> E[As-of evidence check]
  A --> R[Recovery recommendation]
  D --> R
  E --> R
~~~

| Stage | Responsibility |
| --- | --- |
| Normalize | Preserve source event, authority, timestamps, parent/sidechain and exact span provenance. |
| Build intent evidence | Classify attributed user excerpts, compare every required earlier-user pair, retain exact relation/supersession targets, and distinguish incomplete coverage from no detected constraint. |
| Check acknowledgment | Compare the next assistant response to the consequential user message and any explicit repeat-back request. Do not use later assistant prose to repair an earlier omission. |
| Check plan/action | Treat assistant plans as proposals; compare their consequential choices and recorded tool calls with active user intent. The actual tool-call event is an action boundary. |
| Check research warrant | Compare each relevant factual claim with only retrieved evidence available before that boundary. Source requests or agent claims are not evidence. |
| Recommend recovery | Aggregate through a deterministic reducer and return a typed route with event IDs, spans, evidence IDs, as-of times, coverage, and rationale. Keep the route shadow-only. |
| Measure | Report coverage, omissions, incomplete jobs, abstention, routes, latency, and resource use. Review examples separately; do not infer correctness from lane agreement. |

## Success and limits

A usable discovery result has complete source and job accounting, explicit response/intent/research decisions at the defined boundaries, source-grounded route recommendations, and a content-free receipt. If full coverage cannot be established, the affected stream is incomplete and the report says why.

The blind replay can answer whether Laya surfaces plausible, inspectable recovery opportunities in this corpus. It cannot establish live usefulness or generalization on its own. The known incident is reviewed after inference; future unseen sessions are needed for a genuine hidden holdout. Secondary OSS results are reported only if they complete comparable coverage and add distinct reviewed signals.

## Lineage

- Leaf issue: [#28](https://github.com/Pukujan/agent-custom-setup/issues/28); parent: none; dependencies: none; task: ACS-0004.
- Owner problem/scope clarification: [comment #5894826843](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5894826843).
- Primary writer: Codex; branch: task/ACS-25-dual-jev-gates.
