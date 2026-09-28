# TDD — Blind local replay runner

## Test objective

Prove that the replay runner preserves source provenance and temporal boundaries, queries only explicitly configured local decision models, records enough information to detect coverage gaps, and never runs historical tools or Jev. These tests do not measure model accuracy.

## Test layers

### A. Source normalization (offline fixtures)

- Parse human user text, assistant text, tool-use blocks, tool-result blocks, system compact boundaries, and delegated sidechain prompts into distinct event kinds.
- Preserve source UUID, parent UUID, session ID, agent ID, sidechain flag, source path hash, line number, and in-file order.
- Verify role=`user` plus a `tool_result` block never enters the pin classifier.
- Verify sidechain delegated prompts have `authority=agent` and inherit a frozen parent snapshot rather than generating human pins.
- Verify duplicate identical UUIDs collapse once and retain all locations; conflicting UUID content rejects the source.
- Verify timestamp disorder does not reorder causal records or combine unrelated sessions.
- Verify missing/ambiguous causal edges are marked incomplete.
- Verify a compact boundary carries exact preserved message IDs/segments or is rejected as not evaluable.

### B. No-label/no-lookahead reducer

- For user event `u_i`, emit exactly one relation check for every earlier eligible human user event in that stream (or every stable chunk-pair with a parent pair ID).
- Ensure no current/future assistant text, tool result, later correction, gold metadata, or future citation enters the current gate request hash.
- Ensure supersession links target existing prior message IDs; relation history is append-only.
- Apply deterministic hard-deny before any inference client call.
- Check each tool event includes every prior active pin across deterministic groups; exact coverage is recorded, and any omitted/over-budget pin forces `escalate`. A non-allow group runs individual diagnostics without changing the aggregate unless coverage fails.
- Make research readiness consume only prior evidence; incomplete/missing evidence produces `research_more` or `insufficient`, never implicit `ready`.
- Emit no compaction result for a transcript with no captured compact boundary.
- Compare pre/post compaction state using same-lane pins and evidence only.

### C. Local backend contract

- Accept only `http://127.0.0.1`, `http://localhost`, `http://[::1]`, or explicitly allowlisted Tailscale `100.64.0.0/10` endpoints. Reject public names, HTTPS OpenRouter, OpenJev cloud, Jev hostnames, proxy configuration, and redirects to a nonlocal origin.
- Read the declared local model inventory and require exact configured model ID/revision before the first decision request.
- Send schema-valid `/v1/systemone` bodies for `choice`/`noul` decisions and preserve raw model scores.
- Normalize each backend's confidence metadata without pretending semantics are equivalent.
- Reject missing answer keys, unknown choices, NaN/negative/non-normalized probabilities, malformed confidence, hidden truncation indicators, HTTP errors, and mismatched model identity.
- Ensure an unavailable lane stays `not_run`; it never falls back to hosted Jev, OpenRouter, a coding LLM, or another lane.

### D. Metamorphic checks

Implement M01–M14 in `BENCHMARK-PROTOCOL-local-blind-replay.md` using synthetic data only. Every property is checked against serialized requests/receipts and state hashes, not expected labels copied from real transcript incidents.

### E. Integration and replay smoke

1. Run the entire parser/runner against a synthetic source with fake decision responses. Assert deterministic IDs, hashes, event order, and lane isolation.
2. Read-only probe each configured local host for model identity/health. No inference until the identity matches the frozen manifest.
3. Run one synthetic decision per verified model backend and validate the output schema.
4. Run one real Claude source stream using the frozen holdout, then all eligible Claude roots. Store content-free receipts privately.
5. Run ACS/Grok only after a true unlabelled raw source passes the provenance gate. Record missing sources as `not_run`.
6. Re-run exact inputs/config to verify cache determinism. This is repeatability, not accuracy.

## Required commands

```powershell
python -m pytest modules/coordination/jev-oss-compare/v0.1.0/tests/test_local_blind_replay.py -q
python modules/coordination/jev-oss-compare/v0.1.0/scripts/local_blind_replay.py inspect --manifest <private-manifest.json>
python modules/coordination/jev-oss-compare/v0.1.0/scripts/local_blind_replay.py smoke --manifest <private-manifest.json>
python modules/coordination/jev-oss-compare/v0.1.0/scripts/local_blind_replay.py run --manifest <private-manifest.json> --run-id <frozen-run-id>
```

`inspect` and `smoke` must not call a decision endpoint. `run` is the only inference path and must log its backend/model/host list before sending requests. No test uses Jev or OpenRouter.

## Acceptance report

Report exact command, run ID, parser/source hashes, tests passed/failed, endpoints/models verified, inference rows by gate and lane, omitted/incomplete counts, and blockers. Keep raw prompt/output content out of GitHub issue comments and committed files. Do not claim benchmark complete while either source coverage or requested model lanes remain unavailable.
