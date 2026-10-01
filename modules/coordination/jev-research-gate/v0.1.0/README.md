# jev-research-gate v0.1.0 (optional draft)

**Gate (2 of 3):** on a **claim / issue snapshot**, does the agent need external research before coding?

Decisions: `yes` | `no` | `insufficient`.

| Gate | Module |
| --- | --- |
| ambiguity (prompt/resume) | `jev-ambiguity-gate` |
| **research-needed** (this) | `jev-research-gate` |
| tool pin (PreToolUse) | `jev-gate-pin` |

## Fallback
If JEV abstains/errors (`insufficient` / live failure) → use **#14** external research **checklist** (mechanical paperwork). Gates do not remove boss.

## Shared ops
`gate_kind=research` + `issue_snapshots` rows in one `ops.sqlite`. Embeds offline Pass2 only.

## Verify
```bash
python modules/coordination/jev-research-gate/v0.1.0/scripts/research_gate.py --fixture modules/coordination/jev-research-gate/v0.1.0/fixtures/needs_research.json --judge mock --json
python -m pytest modules/coordination/jev-research-gate/v0.1.0/tests -q
```
