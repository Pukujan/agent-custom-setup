# BEHAVIOR — jev-ambiguity-gate
## MUST
- Fire on prompt/resume snapshots.
- Emit `gate_kind=ambiguity` into shared ops.sqlite (+ optional JSONL).
- Default mock judge in CI; live errors → `insufficient` (fail closed for clarity).
## MUST NOT
- Replace boss. Call embeds on hot path. Merge into research or pin modules. Force HOTLOAD base.
