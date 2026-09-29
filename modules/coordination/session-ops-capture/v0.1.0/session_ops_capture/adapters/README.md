# Adapters

Canonical sink is harness-agnostic (`sessions` / `messages` / `tool_calls` /
`gate_events` + Pass2). Each agent hotloading ACS gets a transcript adapter:

| Adapter id | Status | Notes |
|------------|--------|-------|
| `claude-jsonl` | **v0.1 implemented** | Claude Code `~/.claude/projects/.../*.jsonl` |
| `kilo-tasks` | **v0.1 implemented** | Kilo Code VS Code tasks: `globalStorage/kilocode.kilo-code/tasks/<id>/api_conversation_history.json` (+ discovery helpers) |
| `gate-jsonl` | **v0.1 implemented** | jev-gate-pin / ACS gate events |
| `codex-jsonl` | reserved | Codex / OpenAI agent transcripts |
| `grok-jsonl` | reserved | Grok / xAI agent transcripts |
| `generic-jsonl` | reserved | Minimal canonical JSONL if producer already normalizes |

## Kilo discovery (Windows)

Probe with:

```python
from session_ops_capture.adapters import discover_kilo_roots, format_discovery_report
print(format_discovery_report())
```

Observed on Teresa-Pujan: extension `kilocode.kilo-code` 7.8.1 installed;
`%APPDATA%\\Code\\User\\globalStorage\\kilocode.kilo-code` exists; `tasks/`
appears after the first Kilo chat (Cline-style). Until then, pass a fixture or
task folder explicitly: `--adapter kilo-tasks --jsonl <taskDir|api_conversation_history.json>`.

Implement `TranscriptAdapter.ingest_path` → `AdapterResult`; do not fork the DB
or OTLP schema per harness.
