# Claude Code — ACS setup

Source of truth: this repository (`modules/claude-code/`). Desktop `configs/claude-code/` is a **deploy mirror**.

## Launcher (InferHub / LiteLLM)

1. Module: `modules/claude-code/inferhub-litellm/v0.2.0/`
2. Ensure local LiteLLM can start (`D:\claude\litellm\start-litellm.ps1`).
3. Run `launch-claude-inferhub.cmd` or `.ps1` from the module (or Desktop mirror after deploy).
4. Secrets: runtime-only from Desktop `configs\.env` (`LITELLM_MASTER_KEY` / `LITELLM_PROXY_KEY`). **Never commit `.env`.**

See `inferhub-litellm/v0.2.0/NOTES.md`.

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
