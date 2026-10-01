# NOTES — jev-gate-pin operators

- **Optional:** adopters may opt in; **not binding** in `modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md` load-order until proven (FN=0 on block in real runs + Alex accept).
- Registry status is **draft** for v0.1.0.
- Default judge for tests/CI: `--judge mock`. Do not enable InferHub paid calls in CI.
- Knowledge pack remains architecture SoT until this module graduates: `docs/knowledge/jev-architecture-gate-pin-compaction-fish.md`.

- Events use `gate_kind=tool_pin` in shared `ops-db` module.
- Claude PreToolUse hook: `hooks/claude_pretooluse.py` (live). Kilo: stub.
- Sibling gates: ambiguity + research (separate modules).
