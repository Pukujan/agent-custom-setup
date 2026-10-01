# Local OpenJev adapter for fast-jev-compaction

This isolated experiment calls the upstream `fast-jev-compaction` npm library through its documented `compact(messages, asker, options)` contract, with a local Ollama-backed `JevAsker`. It never imports the hosted `JevClient`, TypeSafe credentials, or OpenRouter transport. The default run is a content-free plan; `--execute-local` is required for inference.

The library accepts one ordered Claude-style stream: each message has `role`, `text`, and `toolUses`, with optional `toolResults`; tool calls and results pair by `tool_use_id`. It only judges tool calls/results. User and assistant text stays outside the candidate set, and this runner fingerprints the ordered nonempty text fields before/after and reports only whether they match. It writes no compacted transcript or per-call decisions—only aggregate counts, hashes, package stats, latency and model identity. `corpus.mjs` now converts each raw Claude root/sidechain stream independently and can stage prefix snapshots at captured compact boundaries. It never merges parent/child streams.

## Raw Claude corpus conversion

Run `corpus.mjs` in its default mode to get a private, content-free dry-run receipt. It reads only the raw JSONL tree selected with `--source`; it emits counts, per-file/source/stream hashes, opaque stream IDs, unresolved-link counts, and adapter request estimates. No transcript text is printed or written in dry-run mode, and no model/runtime endpoint is contacted.

```powershell
node .\corpus.mjs --source <private-raw-claude-jsonl-dir> --receipt <private-output-dir>\corpus-plan.json
```

Add `--prepare --output-dir <private-output-dir>\normalized` to write one `{schema_version:1,messages:[...]}` file per stream plus a prefix file for each captured compact-boundary row. Both output paths must be outside this repository; output files use create-only semantics and will not overwrite prior files. Each logical stream and prefix has a unique `run_id` and `run_identity_sha256`; the identity covers source/prefix hash, package version, configured context/reduction settings, and an explicitly unbound model digest. `replay.mjs` creates its own attempt `run_id` unless `--run-id` is supplied, verifies the local Ollama model/digest, then recomputes identity with the verified digest. The actual replay receipt is the source of truth for run aggregation; prepared identities have a null model digest until that verification.

The adapter maps raw text blocks by direct concatenation in their source order, without `.strip()` or inserted separators. The package's `Message` shape has one text field and separate tool arrays, so it cannot represent interleaving between text and tool blocks, image/multimodal content, or thinking/signature blocks. Thinking, redacted-thinking, and signature blocks are excluded by policy; unsupported content is counted and makes that stream ineligible. Tool input structure and result text are retained in prepared private inputs. Calls/results with missing, duplicate, or orphan `tool_use_id` values are counted and make the stream ineligible for replay.

Root and sidechain streams remain separate. Parent links resolve only within their own stream; references to another loaded stream and references absent from all loaded files get separate content-free counts and hashes. No causal parent context is copied into a sidechain. The boundary files are explicitly **source-order prefix approximations**, not proven copies of the exact pre-compaction hook array. Claude's captured boundary metadata supplies a post-boundary preserved-message list in some cases, but the raw transcript does not expose the exact pre-hook message array. Do not present these prefixes as exact reproduction of Claude's compaction input.

Request estimates follow the pinned upstream 0.4.1 rule: paired tool calls whose call/result message falls outside the first and newest six messages are candidates; this adapter makes two serial local HTTP requests per candidate (one call question, one result question). Counts do not include context-fitting failures, process startup, or actual latency. Library token estimation is approximate and it may abridge/drop older state before asking. It performs one compaction decision over a supplied snapshot; it is not an event-by-event pin or research-gate replay.

The input envelope is `{ "schema_version": 1, "messages": [...] }`. Each message is exactly `{ "role": "user"|"assistant", "text": "...", "toolUses": [], "toolResults": []? }`. A tool use is `{ "tool_use_id": "...", "tool": "...", "input": {}, "text"?: "...", "isError"?: false }`; a result is `{ "tool_use_id": "...", "text": "...", "isError"?: false }`. Extra message fields, unmatched/duplicate call IDs, and orphan/duplicate result IDs are rejected, rather than silently normalized away. Preserve source ordering and use a fresh envelope per root conversation; do not combine sidechains.

## Run

Use Node.js 18 or newer. Install the pinned library in this directory:

```powershell
npm ci
node .\replay.mjs --input <private-stream.json> --output <private-receipt.json>
```

That plans locally and performs no model request. A real local replay additionally requires the exact Ollama model name and digest. The example below points at the existing loopback-forwarded OpenJev 9B endpoint; change values only to a verified local identity:

```powershell
node .\replay.mjs --input <private-stream.json> --output <private-receipt.json> `
  --execute-local --base-url http://127.0.0.1:11435 `
  --model 'hf.co/apus-ailab/APUS-OpenJev-v1-9B-GGUF:Q4_K_M' `
  --expected-digest '80f0c6f6f4aaba112195e6877bbc396a572863b0a9e23f33d3fe44dac657385e'
```

Input and receipt paths must be outside the repository. The runner verifies `/api/tags` identity before inference, uses only loopback HTTP with redirects disabled, serializes local requests, and rejects a missing yes/no log-probability pair. It uses raw OpenJev prompting with `think:false`, temperature 0, one generated token and `num_ctx=9216`.

## What the numbers mean

- `fast-jev-compaction` defaults to a 25,000 estimated-token state and 30,000 estimated-token request; those exceed the OpenJev endpoint's 9,216-token context. This runner therefore defaults to 6,000/8,000, which is still an estimate—not tokenizer-exact—and the compactor may abridge or omit old history from the model's view as it fits state. Inspect `stateStage` and `stateTokens` in the aggregate receipt.
- Each candidate tool call gets two local yes/no questions. The library may batch them, but the adapter serializes the individual Ollama calls to avoid competing local requests. The whole fitted history state is repeated for batches, so large sessions can multiply input work. `requests`, local latency, and the source hash are recorded; no per-event payload is retained.
- OpenJev's output is candidate-normalized top-20 token log-probability, not Jev's calibrated probability. If either A or B is absent, this adapter fails closed instead of inventing a score. `keepThreshold` is therefore exploratory; results must not be presented as calibrated confidence or directly compared to TypeSafe Jev.
- No TypeSafe/OpenRouter API billing occurs. Local compute, power, memory pressure, and cost are not measured. Do not run this concurrently with another job using the same 9B model endpoint if avoiding resource contention matters.
- The upstream compactor preserves user/assistant text while pruning tool-use/result blocks, but this is not a user-message pinning or research-gate adapter. It does not replay at every historical event boundary.

## Upstream contract and limits

Pinned npm dependency: `fast-jev-compaction@0.4.1` (Node `>=18`). Its `JevAsker` is `ask(state, questions) -> Promise<{answers}>`; each answer for a `noul` question is `{type:'noul', noul:<P(true)>}`. The compactor itself pairs tool blocks, protects the first and recent messages, and returns a `CompactResult` with the compacted `messages`, per-call `decisions`, and aggregate `stats`. This runner discards message-level outputs after the text-preservation check.

The upstream README documents Claude Code function-hook integration as early access. This lab calls the library directly; it is not a Claude Code hook and does not depend on hook support.
