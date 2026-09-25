# TASK-ACS-0003 — Readme Docs

<!-- continuity:task {"acceptance":["validator VALID on pinned helper f85e88b","README carries the 9 contract sections + 15 references, worked example, evidence table","cite_in_readme URIs appear verbatim in README","continuity validate VALID; no private paths/secrets; touches only README, .content-system, assets, task projection, CURRENT"],"depends_on":[],"goal":"Story-first README + CGM 0.4.0 validator-green adapter (.content-system) for agent-custom-setup","id":"ACS-0003","issue_url":"https://github.com/Pukujan/agent-custom-setup/issues/7","next_action":"author adapter JSON + README + assets, iterate to validator VALID, checkpoint + PR","owner":"owner/Astra (omp session)","priority":"P2","protocol_version":"0.1.0-draft","schema":"project-continuity.task.v1","status":"active","why":"Repo entry point is a stub; owner direction: human-first docs per content-generation-modules specs"} -->

- Status: active
- Owner: owner/Astra (omp session)
- Priority: P2
- Depends on: none

## Goal

Story-first `README.md` + CGM 0.4.0 validator-green `.content-system/` adapter for agent-custom-setup, per https://github.com/Pukujan/content-generation-modules (helper 0.4.0 @ `f85e88b`).

## Why

Owner direction 2026-09-25 ("create readme and docs per its specs for this repo"): `main` README is a placeholder; new readers can't tell who this is for or what is shipped vs pending. AGENTS.md requires human-first docs; this repo already pins CGM 0.4.0 in PR #2's scaffold.

## Allowed files

- `README.md` (rewrite), `.content-system/*.json` (new), `assets/registry-icon.svg`, `assets/IMAGE_NOTES.md`, `tasks/TASK-ACS-0003-readme-docs.md`, `checkpoints/CURRENT.md`

## Human outcome

A newcomer understands within a minute: this is a PCM-governed registry of agent setups, what is on `main` (continuity protocol), what is pending on PRs (#4 oh-my-pi, #2 claude-code scaffold), how secrets stay out, and the deterministic CGM validator gate.

## Scope and boundaries

- In scope: README per `templates/readme-contract.json` v2 (9 sections, 15 references, story order, scan anchors, worked example, evidence table); `.content-system/` adapter per `check_adapter` (system-version.v1 pinned 0.4.0/f85e88b…, brief.v2, brand, visual, manifest, rubric); honest shipped/pending claims.
- Out of scope: image generation (text-first; declare `built-in image_gen` for the visual contract, ship zero narrative rasters); PCM/CI changes; merging #2/#4; private Windows paths.
- Dependencies/uncertainty: `check_narrative_assets` requires literal `generation_workflow: "built-in image_gen"` regardless of raster count — comply + document. Reusing the reviewed `origin/feat/scaffold-pcm-cgm-1`@`8420b78` adapter content, corrected to today's reality, is lowest-risk; every `cite_in_readme` URI must appear verbatim in README; repository_artifact permalinks use full-SHA blob URLs.

## Acceptance criteria

- [ ] `python3 .../validate_content_system.py --root <cgm@f85e88b> --adapter .content-system --project-root .` → `VALID: … and target adapter`, exit 0 (output recorded in checkpoint).
- [ ] README has all 9 `## ` contract headings + all 15 required reference strings + bold scan anchors + a repository-grounded worked example; Evidence-and-boundaries table separates shipped / branch-pending / planned with permalinks.
- [ ] Every `cite_in_readme:true` brief URI appears verbatim in README; every manifest asset path exists.
- [ ] `continuity validate` VALID; secret pattern clean; no `D:\`/`C:\`/`/Users/` in product files.
- [ ] Delivered per PCM: checkpoint on `task/ACS-0003-readme-docs`, #7 receipt, PR `Refs #7`.

## Evidence and sources

- Spec: `Pukujan/content-generation-modules`@`f85e88bc00362c53061d95ac7811bd9c6ada8e32` — `system-version.json`, `templates/readme-contract.json`, `docs/README_PLAYBOOK.md`, `scripts/validate_content_system.py` (`check_adapter`, `check_project_brief_v2`, `check_narrative_assets`, `_valid_repository_permalink`).
- Prior reviewed adapter/README: `origin/feat/scaffold-pcm-cgm-1`@`8420b7876a77b38985b652541071e8cca72288ca` (PR #2, open).
- Repo reality: `main`@`1c44c8d2f25cb71e8acb20253e2cc26cd682af81` (PCM adoption); oh-my-pi @`0b29fdccda48c875fac07b7f087b59609cbbfb99` (PR #4 pending); JEV smoke evidence on issue #3.

## Related records

- Leaf: #7 (parent: none; dependencies: none). Refs #1 (registry pending), #3 (oh-my-pi pending merge).
- Primary writer: omp session (owner/Astra laptop) / branch `task/ACS-0003-readme-docs` / source issue revision: #7 opened 2026-09-25 / as-of: projection current.
- PR/CI + receipts: see #7.

## Checkpoint log

No checkpoints yet.

## Handoff

Read PROJECT → CURRENT → this task → minimum relevant spec. Checkpoint before stopping.
