# NOTES — session-ops-capture v0.1.0

- ACS-wide: any hotloaded agent; Claude JSONL is the first adapter only.
- Live SQLite: `D:\claude\agent-runs\session-ops\` (operator path), not in git.
- Pass2 remote: `ACS_JEV_CLASSIFIER_URL`; embed: `ACS_EMBED_BACKEND=st` + optional
  `sentence-transformers` (not required for CI).
- Proof package receipt scales: same counts/FN fields for 30-turn and longer
  planted-miss sessions.
- Hotload binding deferred.


## Shared ops-db module
Canonical shared SQLite schema/ownership moves to `modules/coordination/ops-db/v0.1.0/` (bi-temporal, namespaced). This module remains the transcript/OTLP/Pass2 embed consumer. Gate JSONL may include `gate_kind` ∈ ambiguity|research|tool_pin. Embeds stay Pass2/offline — never on JEV hot path. Langfuse via OTLP only.
