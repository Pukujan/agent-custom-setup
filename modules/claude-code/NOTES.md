# Claude Code module notes

## What this is

A **sanitized, versioned copy** of the Desktop Claude Code InferHub launcher.
It seats main/advisor models through the local LiteLLM proxy and starts Claude Code.

## Secrets stay outside this repo

- Desktop: `C:\Users\pujan\OneDrive\Desktop\configs\.env`
- InferHub: `D:\claude\inferhub\.env`
- Never paste keys, tokens, or cookies into files under this repository.
- The launcher *reads* `LITELLM_MASTER_KEY` / `LITELLM_PROXY_KEY` at runtime; it does not embed them.

## Expected local layout

| Path | Role |
| --- | --- |
| `D:\claude\litellm` | Unified LiteLLM workbench (`Pukujan/litellm-ckff-ops`) |
| `D:\claude\inferhub` | InferHub-related env (optional for some seats) |
| `C:\Users\pujan\OneDrive\Desktop\configs\claude-code\` | Original live launchers (source of truth for personal tweaks) |

## How to use

1. Ensure the LiteLLM proxy can start (`D:\claude\litellm\start-litellm.ps1`).
2. From this module directory, run `launch-claude-inferhub.cmd` (or the `.ps1`).
3. Pick MAIN model, optional ADVISOR, then a project folder under `D:\claude`.
4. Claude Code starts with `ANTHROPIC_BASE_URL=http://127.0.0.1:4000` and seat alias `sonnet`.

## Temporal metadata

See `module.json` for `version`, `recorded_at` (transaction time), optional `valid_time`,
`source_paths`, and `status`. Update those fields whenever you refresh the sanitized copy
from Desktop.
