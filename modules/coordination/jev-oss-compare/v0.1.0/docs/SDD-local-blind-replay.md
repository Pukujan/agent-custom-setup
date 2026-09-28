# SDD — Blind local decision-model replay

## 1. Runtime boundary

The runner is a deterministic event stepper plus decision-model calls to explicitly configured local endpoints. It has no Jev/OpenRouter client, no browser/research agent, and no tool executor. All historical calls are shadow decisions only.

| Component | Responsibility |
| --- | --- |
| Source adapter | Read raw Claude JSONL and an explicitly approved raw ACS/Grok export; reject known gold-derived artifacts. |
| Provenance normalizer | Emit stable ordered events with session, conversation, role authority, source file/line, UUID, parent UUID, sidechain/agent ID, tool-use ID, and before/after links. |
| State reducer | Maintain one user-message relation graph, active pins, research evidence ledger, and compaction snapshots per stream and model lane. |
| Candidate packer | Deterministically chunk/pack text under the exact checkpoint budget; report original/packed hashes and coverage. No silent truncation. |
| Local decision adapter | Query one named model at a time using `/v1/systemone` or a pinned model-specific adapter; retain the returned score vector and documented confidence meaning. |
| Hard-deny policy | Decide fixed catastrophic tool patterns before any model call. A match records `deny_rule`; it bypasses every model. |
| Receipt writer | Append content-free JSONL results to a private run directory, keyed by run/model/stream/event/prompt hashes. |

## 2. Source event envelope

Normalized event fields:

```json
{
  "event_id": "stable source UUID or deterministic hash",
  "stream_id": "root session + causal agent path",
  "event_index": 0,
  "timestamp": "source timestamp when present",
  "sequence": 0,
  "kind": "human_user|delegated_prompt|assistant_text|tool_call|tool_result|compact_boundary|other",
  "authority": "human|agent|tool|system|unknown",
  "source": {"file_hash": "sha256", "line": 0},
  "uuid": "source UUID",
  "parent_uuid": "source parent UUID or null",
  "is_sidechain": false,
  "agent_id": null,
  "tool_use_id": null,
  "text_ref": "private local content reference",
  "content_sha256": "sha256"
}
```

Text lives in local private storage, never in a committed replay receipt. A role=`user` row is not automatically human intent: tool-result blocks and sidechain delegated prompts are different `kind`/`authority` values. Identical duplicate UUID rows collapse to one event with all source locations retained; conflicting rows sharing a UUID fail the source build. Parent/sidechain links are resolved before replay. A child receives a frozen parent-state snapshot at the delegation event; child user-role prompts do not create human pins.

## 3. Event order and no-lookahead rule

Events are ordered within each source conversation using original array/file sequence as the primary order and timestamps as supporting evidence, not a global timestamp merge. A call sees only state accumulated before that call. The tool result is added only after its corresponding tool-call decision. Future assistant explanations, source outputs, corrections, labels, and compaction results cannot enter earlier states. If causal order is ambiguous, that segment is marked `order_unknown` and excluded from a claim of clean walk-forward coverage.

## 4. Gate definitions

### User-message relation and pin gate

Each eligible human turn `u_i` is compared with every eligible earlier human turn `u_j`, `j < i`, in its stream. The output is a typed relation edge, not a gold pin label:

- `unrelated`
- `same_topic`
- `asks_about_or_questions`
- `adds_constraint_or_refinement`
- `supports_or_commits`
- `revises_or_supersedes`
- `reopens_or_uncertain`
- `unclear`

The runner preserves exact message IDs for every pair. Long messages split into stable, overlapping, sentence-aligned chunks. All chunk pairs are scored; deterministic aggregation retains both pair-level evidence and contradictions. A pin is an attributed user assertion or preference, never a tool result or agent paraphrase. Questions alone do not become hard instructions. Supersession is a graph edge to specific prior message IDs; the model cannot delete or rewrite history.

Separately classify every new human message as `durable_assertion`, `tentative_or_reconsidering`, `question_only`, `context_only`, or `unclear`. Keep every classification as an epistemic record. Only a durable assertion can impose a hard tool constraint; tentative/reconsidering pins can cause escalation, and questions/context do not become tool restrictions. A supersession edge deactivates only the explicitly targeted prior pin after the new message is itself classified; it never erases its history.

### Research-readiness gate

Invoke on each eligible user turn/resume and at coding-start boundaries. The deterministic evidence ledger includes only prior observed source events: URL/repository/version, tool/source kind, retrieved excerpt hash, and whether the cited content addresses the current claim/operation. A frozen lexical-overlap retriever ranks as-of evidence against the latest user/delegated task, the agent's latest readiness claim, and the current coding boundary. It records included and omitted evidence IDs plus a query hash; if potentially matching evidence cannot fit the lane's context budget, the gate is incomplete and cannot say `ready`. The model chooses:

- `research_more`: a required fact/source is missing or unverified;
- `ready`: the as-of evidence is sufficient for the named coding claim;
- `insufficient`: the evidence/task boundary is ambiguous or not representable.

The benchmark does not fetch fresh web pages during replay. It measures what the agent had actually seen by that point. A missing citation, unversioned API, missing source excerpt, or packing gap cannot be silently treated as proof. `ready` is a model prediction, not a verified truth label.

### Tool gate

For every historic tool call, run a fixed deterministic hard-deny list first. On a miss, pack every active pin into deterministic context-bounded groups; each pin's full text is covered exactly, with the same active-pin IDs recorded in the group receipt. The model returns a group verdict: `allow` only when all pins in that group are consistent or irrelevant, `deny` when a durable hard constraint conflicts, and `escalate` when a result is unclear or only a tentative pin conflicts. Non-allow groups trigger individual pin diagnostics to identify likely conflicts. The final tool verdict is a deterministic aggregation of all group verdicts. Missing/capped pin or tool chunks make coverage incomplete and force `escalate`, never `allow`. No historic action executes. Confidence values remain lane-specific observations; this replay does not apply one shared threshold as if Laya, Kev, and OpenJev scores had equivalent calibration.

### Compaction gate

Run only at source-captured `compact_boundary` events. Evaluate active pins/research facts present immediately before the boundary against the captured preserved-message IDs/segment and post-boundary context. Output `preserved`, `partially_preserved`, `lost`, or `insufficient`, plus exact pin/fact IDs. Do not synthesize summaries or infer that a compaction happened from transcript length alone.

## 5. Backend contract

Laya and Kev use the local TypeSafe-compatible `POST /v1/systemone` contract. APUS OpenJev uses its own candidate-scoring prompt served through Ollama `/api/generate` or llama.cpp. These are separate adapters: do not feed APUS OpenJev the System-One JSON shape or interpret its candidate-relative scores as calibrated correctness probabilities.

```json
{
  "model": "exact-configured-checkpoint",
  "state": {"current": "...", "prior": "..."},
  "questions": {
    "relation": {
      "type": "choice",
      "instructions": "Choose the relation between the two attributed messages.",
      "criteria": {
        "unrelated": "No relevant relation.",
        "refines": "The newer message adds a constraint.",
        "supersedes": "The newer message withdraws or replaces the older intent.",
        "unclear": "The evidence does not support a stable relation."
      }
    }
  }
}
```

The adapter supports model-specific input packing and response normalization. It records raw option scores, chosen option, provider confidence field, and confidence definition. It never converts different backends' confidence values to a shared scalar. Model configuration is explicit: `backend`, API root, exact model ID, expected revision, quantization/dtype, device, context tokens, request timeout, and auth environment-variable name. A lane starts only after `GET /v1/models` or its documented equivalent confirms the expected endpoint/model. Unknown models and nonlocal hosts fail closed.

Initial requested roster:

| Lane | Requested location | Candidate identity | Context risk |
| --- | --- | --- | --- |
| Laya | PC | typed-decisions checkpoint, revision pinned | 1,024-token state limit; CPU smoke passed |
| OpenJev 4B | PC | APUS OpenJev v1 4B Q4_K_M | Installed and smoke-tested; top-20 logits may be incomplete |
| OpenJev 9B | MacBook Pro | APUS OpenJev v1 9B Q4_K_M | Installed and smoke-tested through SSH port-forward |
| Kev 0.8B | PC | `jaredpalmer/kev-0.8b@9a45d25eb2ab761841196625383fa1dff0e56c1e`, base `Qwen/Qwen3.5-0.8B-Base@dc7cdfe2ee4154fa7e30f5b51ca41bfa40174e68` | Installed, identity-probed, CPU synthetic smoke passed |
| Kev 4B/9B | PC or Mac | Not installed | Not included in run roster; 9B BF16 exceeds observed memory and 4B capacity/quantized serving is unverified |

OpenJev/Kev are not Jev. Synthetic smokes confirm local adapter/API viability only; no transcript replay has run. No cloud fallback is allowed.

Raw Claude normalization yields 18,350 events across 80 streams (14 root sessions, 66 child streams), 2,210 repeated rows, zero malformed lines, and 56 of 66 child streams linked to a unique parent. Ten unresolved sidechains cannot inherit parent state. Forty-six `isMeta=true` rows are classified `meta_user`, leaving 198 human-user events. Raw compaction metadata provides retained UUID lists but no summary prose; semantic survival of an omitted pin is unknown. Three additional independent Claude worktree roots contain 1,008 events total. No raw Grok source is verified.

## 6. Determinism, caching, and privacy

- Freeze source bytes/hashes, parser revision, prompt/schema hashes, model revisions, model settings, retrieval settings, confidence semantics, and session split before any live output is reviewed.
- Cache key includes the complete request hash, backend/model revision, and runtime settings. A cache hit is replayed only for identical inputs.
- Model lane states are isolated. One model's pins, outputs, cache entries, or confidence cannot feed another model.
- Use one in-flight request per host by default; this is explicitly configurable only after stable single-request smoke. Separate host queues prevent PC and Mac workloads from competing for memory.
- Private source text and raw model payloads remain outside Git. Committed evidence is code, schemas, prompts, source-manifest hashes, and aggregate content-free receipts.
- Local networking uses no system proxy and permits only loopback or explicitly listed tailnet IPs. Any attempt to contact Jev, OpenRouter, public Hugging Face inference, or an unlisted host aborts.

## 7. Failure handling

Timeout, HTTP error, schema error, model mismatch, state overflow, malformed probability vector, and missing confidence semantics are logged per lane. No fallback changes model or endpoint. The gate result for that event is `insufficient`/`escalate`; later events may continue in a separately marked degraded stream but cannot report complete coverage. The runner never executes tool calls or mutates the original transcript.

## 8. Receipt shape

Each receipt records run ID, source hash, parser version, event ID/index/kind, stream hash, lane/model/checkpoint, request hash, packed coverage, candidate message/pin IDs, raw probability map, chosen label, confidence field/definition, latency, error, and next-state hash. No raw message, tool args, tool results, URL query secret, or prompt body is emitted by default.
