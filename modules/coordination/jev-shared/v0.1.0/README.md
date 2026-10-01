# jev-shared v0.1.0

Tiny shared helpers for the **three** ACS JEV gate modules:

1. `jev-ambiguity-gate` — prompt/resume ambiguity
2. `jev-research-gate` — research-needed on claim snapshots
3. `jev-gate-pin` — PreToolUse tool pin gate

## Shared ops DB (binding)

**ONE** local SQLite: `ops.sqlite` (default under session-ops data dir / `ACS_OPS_DB`).
Used by: transcript ingest, **all three** gate event kinds, issue/claim snapshots, embeddings.

- Langfuse: **OTLP only** (via session-ops `otlp.py` → Gravebuster → Langfuse). No Langfuse SDK/keys in gate modules.
- Embedder: cheap local **nomic-class** (or hashing stub in CI), **batched/offline Pass2** — **never** on the JEV hot path.

## Layout

- `openrouter_jev.py` — mock + live `typesafe/jev-1.13` decisions API
- `ops_db.py` — append `gate_events` / `issue_snapshots` into shared ops.sqlite
- `redact.py` — secret scrub for notes/payloads
