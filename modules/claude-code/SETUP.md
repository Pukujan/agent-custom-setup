# Claude Code — ACS setup

This folder holds the ACS-side Claude Code docs: the optional JEV hook gates and how transcripts feed the shared ops database.

## Launcher (InferHub / LiteLLM)

The Claude Code + InferHub launcher (Windows and Mac) moved out of ACS. It now lives in the private repo [Pukujan/claude-code-launcher](https://github.com/Pukujan/claude-code-launcher); setup steps, secrets handling and deploy notes are there. The old `inferhub-litellm` module was removed from this repo in #66.

## Optional JEV seatbelts (HOTLOAD full)

| Module | Hook / fire point | Live vs stub |
| --- | --- | --- |
| `jev-ambiguity-gate` | UserPromptSubmit / SessionStart | Claude hook **live**; Kilo **stub** |
| `jev-research-gate` | Claim / issue snapshot | Claude hook **live**; Kilo **stub**; #14 checklist fallback |
| `jev-gate-pin` | PreToolUse | Claude hook **live**; Kilo **stub** |
| `ops-db` | shared SQLite | **live** schema/API |
| `session-ops-capture` | transcript + OTLP | Claude JSONL **live**; Kilo tasks **live** adapter |

Hook install details: each gate's `HOOKS.md` / `hooks/`.

## Transcripts

Claude Code stores project transcripts under `~/.claude/projects/<encoded-cwd>/` (JSONL). session-ops `claude-jsonl` adapter ingests these into shared `ops-db`.
