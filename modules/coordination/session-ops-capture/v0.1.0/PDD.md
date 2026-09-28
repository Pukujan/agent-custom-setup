# PDD — session-ops-capture v0.1.0

## Problem

Agents that hotload ACS (Claude Code, and later Codex / Grok / others) produce
tool-rich sessions, but ACS launchers do not create a shared ops trail. Operators
cannot answer: *when did tools fire, did a gate run, what is the risk/research
label, and can we search similar tool text?* across harnesses.

Gravebuster already runs OTEL collector → Langfuse (`:4318` / UI `:3000`). A
second observability stack would duplicate cost and keys.

## Desired outcome (v0.1 done-when = Pass1 **and** Pass2)

### Pass1 — deterministic trail
1. Normalized SQLite buffer: `sessions`, `messages`, `tool_calls`, `gate_events`
   (uuid-keyed, idempotent).
2. **Adapter interface** — Claude Code JSONL is **adapter #1**; Kilo Code
   (VS Code) tasks are **adapter #2**; Codex/Grok/etc. plug in without forking
   the schema.
3. OTLP/HTTP spans to Gravebuster (`service.name=acs.session-ops-capture`) with
   `session_id`, `cwd`, `tool.name`, `tool.decision`, `interaction.index`.
4. Optional `gate-jsonl` ingest into the same DB + OTLP stream.
5. Redaction so secrets never land in SQLite or spans.

### Pass2 — classify + embed (same module)
1. Batch/live classify of tool_calls/messages → `risk_class`, `research_needed`,
   `gate_relevant`, labels (mock judge for pytest; real InferHub/JEV URL when env
   configured; CI fail-closed to mock).
2. Local embedding table for searchable tool/message text (hashing backend
   default; optional sentence-transformers / nomic when installed). Counts stay SQL;
   vectors = search.
3. Held-out FN=0 planted-miss fixtures; receipt schema scales beyond the first
   ≥30-interaction live slice to longer sessions.

## Non-goals (v0.1)
- Hard-coding Claude as the only source forever (Kilo is required in v0.1)
- Replacing Gravebuster / putting Langfuse keys in code
- Binding into `HOTLOAD.md` until proven
- Blocking CI on paid classify/embed APIs

## Success metrics
| Metric | Threshold (proposed) |
|--------|----------------------|
| pytest | green (Pass1+Pass2+FN0+metamorphic) |
| Metamorphic Pass1 | reorder/dup JSONL → same fingerprint |
| Metamorphic Pass2 | re-classify → same labels; embed same text → cosine≈1 |
| FN=0 held-out | no missed `gate_relevant` on planted set |
| Live slice | ≥30 tool_calls; OTLP 2xx; classify+embed rows present |

## Stakeholders
ACS operators for **any** hotloaded agent; Gravebuster/Langfuse consumers.
