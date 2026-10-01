# jev-ambiguity-gate v0.1.0 (optional draft)

**Gate (1 of 3):** user **prompt / session resume** clarity.

| Gate | When | Decisions |
| --- | --- | --- |
| **ambiguity** (this) | UserPromptSubmit / SessionStart / resume | `clear` / `ambiguous` / `insufficient` |
| research-needed | Claim / issue snapshot | `yes` / `no` / `insufficient` |
| jev-gate-pin | PreToolUse (tool) | `allow` / `deny` / `escalate` |

Do **not** collapse into research-needed.

## Authority
You/GitHub issue → Boss ACCEPT/REJECT → JEV seatbelts → coder.

## Shared ops
`gate_kind=ambiguity` → one ACS `ops.sqlite`. Embeds never on hot path. Langfuse via OTLP only (session-ops).

## Verify
```bash
python modules/coordination/jev-ambiguity-gate/v0.1.0/scripts/ambiguity_gate.py --fixture modules/coordination/jev-ambiguity-gate/v0.1.0/fixtures/clear_prompt.json --judge mock --json
python -m pytest modules/coordination/jev-ambiguity-gate/v0.1.0/tests -q
```
