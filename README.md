# agent-custom-setup

> **Your customized agent launchers deserve a versioned registry — without putting secrets into git.**

## Why this exists

On a busy workstation, a Claude Code launcher often lives as a Desktop script: it works, until it drifts.
Another agent cannot tell which copy is current, when it was recorded, or whether someone pasted an API key into the file.
**Desktop one-offs do not version themselves.**

This repository exists so those setups can be registered as modules with explicit versions and temporal metadata, while secrets stay in the Desktop and InferHub `.env` files that already hold them.

## What this project is

**agent-custom-setup** is a private modular registry of custom agent setups.
It is for operators who keep launchers on a personal machine, and for agents that need a sanitized, inspectable copy.

It is **not** a secrets vault, not a hosted agent platform, and not a claim that every launcher works on every machine.

## What you can make or use

- A `registry.json` index of modules with `version`, `recorded_at`, optional `valid_time`, `source_paths`, and `status`
- Versioned modules under `modules/<id>/` with `module.json`, files, and `NOTES.md`
- The first module: **claude-code** — sanitized InferHub + local LiteLLM launcher copies
- CGM adapter under `.content-system/` pinned to helper **0.4.0** for evidence-bound README work
- PCM / Continuity files for project continuity once initialized

## How it works

1. **Register** a module in `registry.json` with temporal metadata.
2. **Store** sanitized files under `modules/<id>/` plus operator notes.
3. **Keep secrets outside** — Desktop `configs/.env` and InferHub `.env` remain the only places for keys.
4. **Refresh** by bumping module `version` / `recorded_at` when Desktop launchers change.

The Claude Code module seats InferHub Top-20 models through the local LiteLLM proxy at `http://127.0.0.1:4000`, then starts Claude Code with seat alias `sonnet`.

## Evidence and boundaries

| Claim | What the evidence supports | What it does not establish | Source |
| --- | --- | --- | --- |
| Modular registry with temporal metadata | Scaffold includes `registry.json`, schemas, and module metadata fields | Long-term multi-module adoption | [https://github.com/Pukujan/agent-custom-setup/issues/1](https://github.com/Pukujan/agent-custom-setup/issues/1) |
| First module is sanitized Claude Code launcher | `modules/claude-code/` holds `.ps1`/`.cmd` plus secrets policy | Desktop originals will never change | [`module.json` @ `804f9e3`](https://github.com/Pukujan/agent-custom-setup/blob/804f9e350320af49e7c66811144a91600b185844/modules/claude-code/module.json) |
| Narrative README images TBD | `assets/IMAGE_NOTES.md` records text-first shipping | First-screen marketing visuals exist | [`IMAGE_NOTES.md` @ `804f9e3`](https://github.com/Pukujan/agent-custom-setup/blob/804f9e350320af49e7c66811144a91600b185844/assets/IMAGE_NOTES.md) |

**Boundaries:** never commit API keys, tokens, cookies, or `.env` contents. Do not treat this repo as a substitute for Desktop configs. Narrative raster images are planned, not shipped.


## Image generation and use

Narrative hero/problem rasters are **not generated yet** on this machine.
See [`assets/IMAGE_NOTES.md`](assets/IMAGE_NOTES.md). A small non-narrative SVG icon ships at [`assets/registry-icon.svg`](assets/registry-icon.svg).
When image generation is available, record full provenance in `.content-system/asset-manifest.json` before linking images from this README.

## Templates and guides

- Project brief: [`.content-system/project-brief.json`](.content-system/project-brief.json)
- Brand language: [`.content-system/brand-language.json`](.content-system/brand-language.json)
- Visual style: [`.content-system/visual-style.json`](.content-system/visual-style.json)
- Asset manifest: [`.content-system/asset-manifest.json`](.content-system/asset-manifest.json)
- Helper playbook (pinned checkout): `D:\claude\content-generation-modules\docs\README_PLAYBOOK.md`

## Prior work and references

- CGM helper `Pukujan/content-generation-modules` @ `0.4.0` (`f85e88bc…`)
- Adapter pattern referenced from `D:\claude\eval-lab\.content-system\` (updated here to helper 0.4.0 + project-brief v2)
- LiteLLM operations sibling: [`Pukujan/litellm-ckff-ops`](https://github.com/Pukujan/litellm-ckff-ops)

## Try it

```bash
gh repo clone Pukujan/agent-custom-setup
cd agent-custom-setup
```

Claude Code module path:

```text
modules/claude-code/
  module.json
  launch-claude-inferhub.ps1
  launch-claude-inferhub.cmd
  NOTES.md
```

On the operator machine, run `modules\claude-code\launch-claude-inferhub.cmd` after the local LiteLLM workbench at `D:\claude\litellm` can start. Ensure Desktop `configs\.env` provides `LITELLM_MASTER_KEY` or `LITELLM_PROXY_KEY`.

### Scan test

Headings + bold anchors should recover: Desktop drift problem → versioned sanitized registry → claude-code module → secrets stay outside → clone and open `modules/claude-code/`.
