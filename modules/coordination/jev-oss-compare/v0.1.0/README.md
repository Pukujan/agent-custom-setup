# jev-oss-compare v0.1.0

Comparison lane for ACS JEV gates vs OSS peers. Does **not** replace ACS HOTLOAD defaults.

## Decision table

| Candidate | Verdict | Why | Proof |
| --- | --- | --- | --- |
| jomatsu/pi-jev-auto-mode | **ADAPT_PATTERN** | Hard-deny→rules→Jev; Pi package will not run on Claude/Kilo; port into compare peer | [repo](https://github.com/jomatsu/pi-jev-auto-mode) · [policy.test.ts](https://github.com/jomatsu/pi-jev-auto-mode/blob/main/test/policy.test.ts) |
| TheoOliveira/pi-jev (jev-gate) | **ADAPT_PATTERN** | Post-run criteria stub only | [gate.ts](https://github.com/TheoOliveira/pi-jev/blob/main/src/gate.ts) · [gate.test.ts](https://github.com/TheoOliveira/pi-jev/blob/main/test/gate.test.ts) |
| jkudish/jev-mcp | **USE** (optional dep/CLI) | MCP + node:test; ACS keeps packer+hooks | [package.json](https://github.com/jkudish/jev-mcp/blob/main/package.json) |
| ctmx/openrouter-jev-mcp | **ADAPT** / thin helper | ACS already has `jev-shared/openrouter_jev.py` | [README](https://github.com/ctmx/openrouter-jev-mcp) |
| tamaratran/fast-jev-compaction | **SKIP** (later OK) | Compaction not tool-gate | [README](https://github.com/tamaratran/fast-jev-compaction) |
| browser-use/jev-ultrafast | **SKIP** | Pure browser | [README](https://github.com/browser-use/jev-ultrafast) |
| FuJuntao/pi-permission-gate | **ADAPT_PATTERN** (ref) | Overlaps auto-mode catalogue | [README](https://github.com/FuJuntao/pi-permission-gate) |
| can1357/oh-my-pi | **SKIP** | No distinct ACS drop-in tool gate | [README](https://github.com/can1357/oh-my-pi) |

## Prefer which

| Need | Prefer |
| --- | --- |
| Live Claude PreToolUse / Kilo veto | ACS `jev-gate-pin` |
| Catastrophic bash hard-deny envelope | Compare peer (auto-mode patterns); not live yet |
| Post-run acceptance criteria | `adapters/jev_gate_post_run_stub.py` |
| Typed MCP judgments | Optional `jkudish/jev-mcp` |

## Bench

```bash
ACS_JEV_LIVE=1 python modules/coordination/jev-oss-compare/v0.1.0/scripts/compare_run.py --cap 12 --workers 6 --append-html
python -m pytest modules/coordination/jev-oss-compare/v0.1.0/tests -q
```

Report: [`reports/jev-oss-compare.html`](reports/jev-oss-compare.html) (appendable).
