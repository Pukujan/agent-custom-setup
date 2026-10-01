# TDD — session-ops-capture v0.1.0

## Layers
1. **Red unit tests** — redaction strips `sk-`/`ghp-`/bearer/`api_key=`
2. **Pass1 idempotency / metamorphic** — duplicate/reorder → same fingerprint
3. **Pass2 metamorphic** — re-classify → same labels; embed same text → cosine≈1
4. **FN=0 held-out** — `tests/fixtures/held_out_fn0/` planted gate-relevant tools
5. **OTLP shape** — no live network in unit tests
6. **Adapters** — `claude-jsonl` + `gate-jsonl` registered

## Commands
```powershell
cd modules\coordination\session-ops-capture\v0.1.0
python -m pytest -q
```

## Live evidence (issue #22 receipt)
1. Scratch dir preferred; ingest synthetic ≥30 tools + held-out plants + mock gate.
2. Confirm SQLite counts for Pass1+Pass2; OTLP POST 2xx.
3. Optional short real harness probe via Claude adapter (other adapters later).
4. Comment receipt: counts, sample queries, OTLP endpoint, Langfuse UI
   `http://100.93.66.34:3000`, FN=0 result. No invented trace IDs; no secrets.

CI must not require paid APIs — mock/hash fail-closed.
