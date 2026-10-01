# ops-db v0.1.0 (optional draft — HOTLOAD **full** dependency)

**Own versionable ACS module** for the **one** shared local SQLite used by session-ops + three JEV gates.

## Lasting proof vs buffer (binding)

| Lasting proof (ONLY) | Ephemeral buffer (this DB) |
| --- | --- |
| **git** history | transcript / tool_call noise |
| **GitHub issues** / PR evidence comments | gate_events |
| **benchmarks** / eval fixtures | embeds + Pass2 classify aids |

**ops.sqlite is NOT a self-learning forever store.** Embed/classify are ephemeral aids.

## Per-partition FIFO (RESEARCH-ALIGNED lock, #25)

ONE file; caps are **per stream**, not one global FIFO:

| Partition | Policy |
| --- | --- |
| `transcript_tool_calls` / messages | **Short** FIFO (dies fast; default 3d / 20–30k) |
| `gate_events` | **Longer** (default 30d / 20k) |
| `claim_snapshots` / `pin_snapshots` | **Not** evicted with tool spam; own long caps (90d / 5k) |
| `embed_vectors` | Same FIFO **family as parent stream**; batched offline nomic-class; **never on JEV hot path** |

## Temporal (fossil-style)

Append-only rows with `occurred_at` + `recorded_at`.
**As-of** = `recorded_at <= T`, then **replay prefix** in `recorded_at` order (not classic bi-temporal SQL unless a bench forces it).

## Embeds vs JEV hot path

Gate decisions (ambiguity / research / tool pin) are **deterministic** — no embed lookup, no numpy, no vector scan on that path.
Embeddings live as float32 BLOBs here; similarity is offline numpy exact scan (session-ops `embed_scan.py`) only.

## Langfuse

OTLP only via session-ops → Gravebuster → Langfuse. No Langfuse keys here.

## Verify
```bash
python -m pytest modules/coordination/ops-db/v0.1.0/tests -q
```
