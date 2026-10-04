# How Claude Code works here (checked local vs official docs)

## Checked locally (Teresa-Pujan, 2026-09-28)

| Path | Observed role |
| --- | --- |
| `~/.claude/settings.json` | User settings: permissions allow-list, `model` / `modelPicker` InferHub seats (`sonnet`, `opus`, `ih/...`) |
| `~/.claude/projects/` | Per-project session dirs (encoded cwd), JSONL transcripts |
| `~/.claude/history.jsonl` | History index |
| Claude Code + InferHub launcher | Lives in [Pukujan/claude-code-launcher](https://github.com/Pukujan/claude-code-launcher), no longer in ACS (#66) |

## Official docs (hooks) — summary checked against public Claude Code hooks guides (2026)

- Hooks configured under `hooks` in `~/.claude/settings.json`, project `.claude/settings.json`, or `.claude/settings.local.json`.
- **PreToolUse**: runs after tool params built, before execution. Matcher on tool name (`Bash`, `Edit|Write`, `*`, …).
- stdin: JSON event; stdout may include `hookSpecificOutput.permissionDecision` = `allow` | `deny` | `ask`.
- Exit code **2** on PreToolUse is the classic block signal (stderr → model); JSON permissionDecision is preferred in newer docs.
- Related events ACS uses: `UserPromptSubmit` / `SessionStart` (ambiguity), `PreToolUse` (tool pin), SessionStart/manual (research claim snapshot).

## ACS mapping

```
prompt/resume → jev-ambiguity-gate
claim snapshot → jev-research-gate (#14 checklist fallback)
tool call → jev-gate-pin
all events / transcripts / embeds → ops-db (bi-temporal) + session-ops OTLP
```

Boss ACCEPT/REJECT remains above JEV seatbelts.
