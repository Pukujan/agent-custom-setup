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

### 2026-09-25 23:09:55 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["None for this task. Note: repo-wide ci enforcement still blocked by Actions runner capacity (ACS-0002/#5); PR #7 for this increment will show a failing/absent ci until #6 lands \u2014 merge of this docs increment must not be labeled gated by required checks."],"changed":["README.md, .content-system/*.json (6 new), assets/registry-icon.svg, assets/IMAGE_NOTES.md, tasks/TASK-ACS-0003-readme-docs.md, checkpoints/CURRENT.md"],"completed":["ACS-0003 delivered on task/ACS-0003-readme-docs: story-first README.md per CGM readme-contract v2 (9 sections incl. Evidence and boundaries with shipped/pending honesty, 15 pinned references, worked example from issue #3, bold scan anchors, code fences after story) + .content-system/ adapter (system-version.v1 pinned helper 0.4.0@f85e88b, project-brief.v2 with 5 evidence items all cite_in_readme:true, brand-language, visual-style with generation_workflow built-in image_gen, asset-manifest with single non-narrative SVG, review-rubric) + assets (icon, IMAGE_NOTES) + projection + CURRENT repoint."],"decisions":["Sequential canonical-checkout work, not a managed worktree: an in-repo worktree for ACS-0003 broke continuity validate in both trees (validate_managed_worktrees requires the ACS-0003 projection in the canonical tasks/), observed INVALID x2 -> tree removed, work moved here. Claims re-pinned to today's reality vs the 8420b78 draft: claude-code registry downgraded shipped->planned (PR #2 unmerged), oh-my-pi marked shipped-on-task-branch behind PR #4, issue #3 JEV evidence cited as user_observation, all D:\\ paths removed."],"evidence":["Validator: python3 <cgm@f85e88b>/scripts/validate_content_system.py --root <cgm> --adapter .content-system --project-root . -> 'VALID: content-generation-modules contract and target adapter' exit 0 (observed 2026-09-25). Audit script: 0 missing sections, 0 missing references, 23 bold anchors, why-before-how true, code-after-story true. grep D:\\|C:\\|/Users/|secret-patterns -> clean; every cite_in_readme URI substring present in README. continuity validate VALID; preflight TARGET_VALID. Product 12db50f on task/ACS-0003-readme-docs."],"next_action":"Publish #7 receipt keyed to request id + pushed SHA; open PR task/ACS-0003-readme-docs -> main with Refs #7; owner reviews/merges (no required checks exist yet); after merge close #7 and mark CURRENT.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0003","timestamp":"2026-09-25T23:09:55Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"daa9f5c7526c6bf551a7c46c4ee1ee88fb89fbdcaffdaaf6818909ad06fcb698","request_id":"acs-0003-docs-20260925","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0003"} -->

Completed:
- ACS-0003 delivered on task/ACS-0003-readme-docs: story-first README.md per CGM readme-contract v2 (9 sections incl. Evidence and boundaries with shipped/pending honesty, 15 pinned references, worked example from issue #3, bold scan anchors, code fences after story) + .content-system/ adapter (system-version.v1 pinned helper 0.4.0@f85e88b, project-brief.v2 with 5 evidence items all cite_in_readme:true, brand-language, visual-style with generation_workflow built-in image_gen, asset-manifest with single non-narrative SVG, review-rubric) + assets (icon, IMAGE_NOTES) + projection + CURRENT repoint.

Evidence:
- Validator: python3 <cgm@f85e88b>/scripts/validate_content_system.py --root <cgm> --adapter .content-system --project-root . -> 'VALID: content-generation-modules contract and target adapter' exit 0 (observed 2026-09-25). Audit script: 0 missing sections, 0 missing references, 23 bold anchors, why-before-how true, code-after-story true. grep D:\|C:\|/Users/|secret-patterns -> clean; every cite_in_readme URI substring present in README. continuity validate VALID; preflight TARGET_VALID. Product 12db50f on task/ACS-0003-readme-docs.

Decisions:
- Sequential canonical-checkout work, not a managed worktree: an in-repo worktree for ACS-0003 broke continuity validate in both trees (validate_managed_worktrees requires the ACS-0003 projection in the canonical tasks/), observed INVALID x2 -> tree removed, work moved here. Claims re-pinned to today's reality vs the 8420b78 draft: claude-code registry downgraded shipped->planned (PR #2 unmerged), oh-my-pi marked shipped-on-task-branch behind PR #4, issue #3 JEV evidence cited as user_observation, all D:\ paths removed.

Changed:
- README.md, .content-system/*.json (6 new), assets/registry-icon.svg, assets/IMAGE_NOTES.md, tasks/TASK-ACS-0003-readme-docs.md, checkpoints/CURRENT.md

Blocked/uncertain:
- None for this task. Note: repo-wide ci enforcement still blocked by Actions runner capacity (ACS-0002/#5); PR #7 for this increment will show a failing/absent ci until #6 lands — merge of this docs increment must not be labeled gated by required checks.

Next:
- Publish #7 receipt keyed to request id + pushed SHA; open PR task/ACS-0003-readme-docs -> main with Refs #7; owner reviews/merges (no required checks exist yet); after merge close #7 and mark CURRENT.

## Handoff

Read PROJECT → CURRENT → this task → minimum relevant spec. Checkpoint before stopping.
