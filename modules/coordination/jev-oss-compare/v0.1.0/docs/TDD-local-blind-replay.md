# TDD — Recovery-routing replay and validation

## Test objective

Validate that the benchmark preserves source authority, chronology, as-of evidence, exact coverage and route provenance, and that the decision contract can represent consequential acknowledgment misses, intent conflicts, research gaps and useful recovery recommendations. Synthetic tests validate mechanics and decision sensitivity; they do not establish model accuracy or live recovery.

## A. Source and authority tests

- Parse human text, assistant responses/proposals, tool calls, tool results, research-source results, delegation, and captured compaction into distinct events with UUIDs, parents, sidechain IDs, source lines, timestamps and sequence.
- Ensure tool-result text, agent plans, delegated prompts and search requests never become human intent or retrieved supporting evidence.
- Ensure duplicate identical IDs collapse while retaining all locations; conflicting IDs reject the source.
- Ensure file sequence remains causal when timestamps are delayed, repeated, or out of order.
- Ensure unresolved task/parent context is explicit and cannot be silently inherited.
- Verify source and event manifests reject curated labels or incomplete streams as blind evidence.

## B. Intent ledger and reducer tests

- Emit every eligible earlier-user pair in the same stream and every required span-pair job; record expected, scored, skipped and failed jobs.
- Preserve exact user-message and span IDs through relation aggregation.
- Apply explicit supersession only to the exact target span; a partial correction cannot deactivate unrelated clauses.
- Preserve durable instructions through arbitrary time delays unless an exact supersession or clear task boundary exists.
- Treat uncertain task context, mixed chunk results, state overflow, queue loss, or missing jobs as incomplete.
- Check that a missing active pin set is distinguishable from complete source coverage with no detected constraints.

## C. Acknowledgment, action, and research tests

- Compare a consequential user instruction only with its next assistant response; later messages cannot repair the acknowledgment receipt.
- Cover accurate, partial, omitted, contradicted and unclear acknowledgment states, including explicit repeat-back requests.
- Check a later conflicting plan/action even if the assistant previously acknowledged the user correctly.
- Keep plan/proposal events distinct from recorded tool actions; no prose may be reported as an executed action.
- For each claim, use only prior retrieved source evidence and record source identity/version/as-of time plus exact excerpt span/hash.
- Distinguish direct support from citation-only text, search requests, agent claims, stale/wrong-version sources, contradictions and missing results.
- Ensure missing evidence can recommend research_more or dispatch_verifier with the exact claim/source gap; the replay never starts a verifier.
- Verify a durable conflict holds only the affected action while unrelated safe work remains independently eligible.

## D. Recovery schema and privacy tests

- Accept only reconfirm_intent, rethink_plan, research_more, dispatch_verifier, escalate, and proceed.
- Require a reason, target checkpoint, evidence/intent IDs, coverage status, source time and decision receipt time.
- Reject proceed when a required input/job is missing, truncated, malformed or contradictory.
- Preserve raw model scores and lane-specific confidence semantics.
- Ensure content-free receipts include hashes and identifiers but no transcript text, tool payload, source body, secret, or prompt.

## E. Metamorphic and generated fuzz validation

- Implement M01–M28 from BENCHMARK-PROTOCOL-local-blind-replay.md using synthetic data only.
- Run a deterministic grammar/property fuzzer over scope, negation, paraphrase, order, irrelevant history, delays, partial corrections, task/sidechain boundaries, acknowledgment omissions, source versions, future evidence and truncation.
- Assert invariants and paired sensitivity: irrelevant changes preserve routes; removing a required constraint/source changes the affected route or yields explicit uncertainty; no future event changes an earlier decision hash.
- Store deterministic seeds and content-free failure receipts. Do not add named transcript incidents as generated fixtures.
- Fuzz mechanics broadly; have blinded human review evaluate a sample of semantic model recommendations. Do not claim the fuzzer supplies gold labels.

## F. Holdout policy

- Do not reuse or rename the earlier post-inference partition as hidden.
- A genuine hidden holdout must select complete unexposed root sessions and descendants before the frozen prompt/schema/profile is run, keep outputs sealed during any iteration, and publish only source/split hashes.
- The current full transcript replay is exploratory unless an actually unexposed root/session is proven. With no valid holdout, mark holdout not_run; use a fresh future transcript for generalization claims.
- A held-out unlabeled split tests stability and leakage, not accuracy. Review routed and unrouted consequential samples after inference; keep human findings separate from model output.

## G. Local lane and full replay

1. Validate the source manifest, event coverage, parser version and frozen run identity without calling a model.
2. Verify the exact local Laya checkpoint, SDK, runtime and resource budget. Use a bounded synthetic request before transcript input.
3. Run deterministic synthetic reducers and the metamorphic/fuzz suite with fake model outputs. No hosted Jev/OpenRouter fallback.
4. Freeze the Laya-first profile and all hashes; then run the verified raw Claude corpus in source order and account for every planned job.
5. Consider OpenJev or Kev only if a distinct miss hypothesis remains and they can receive comparable inputs/coverage. Record unavailable or unneeded lanes as not_run.
6. After the blind run is frozen, inspect known incidents and a blinded sample of alerts/unalerted checkpoints. Do not tune and call the same output a hidden evaluation.
7. Produce a content-free report with coverage, routes, incomplete reasons, performance, audit limitations and next action.

## Required implementation evidence

- A test report for source, reducer, acknowledgment, action/research route, privacy, M01–M28 and generated fuzz properties.
- A frozen profile and run manifest with exact model/checkpoint/runtime/source hashes.
- A content-free receipt for every planned decision job, including failures, skips, and routes.
- A truthful holdout status; no accuracy or live-recovery claim unless backed by an independent evaluation.

The prior targeted synthetic adapter suite passed 9 tests for acknowledgment and source-evidence mechanics. The suite has since expanded to 12 cases to cover assistant prose-boundary classification and plan-to-intent routing. Its latest run reported 11 passed and one fixture mismatch; the fixture was corrected afterward, but the suite has not been rerun. These tests validate mechanics only; they do not establish Laya decision quality, the full M01-M28 suite, generated fuzz coverage, or transcript performance. No Laya inference or full-transcript run has occurred.

## Lineage

Owning leaf issue: [#28](https://github.com/Pukujan/agent-custom-setup/issues/28); parent: none; dependencies: none. Task ACS-0004; primary writer Codex; branch task/ACS-25-dual-jev-gates. Scope correction: [comment #5894826843](https://github.com/Pukujan/agent-custom-setup/issues/28#issuecomment-5894826843).
