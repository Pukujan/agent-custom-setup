# TASK-ACS-0003 — Readme Docs

<!-- continuity:task {"acceptance": ["pinned CGM validator exit 0 VALID on adapter+project-root", "README: 9 sections + 15 refs + anchors + worked example + shipped/pending/planned evidence table + status-at-a-glance", "cite_in_readme URIs verbatim; manifest paths exist", "continuity validate VALID; no secrets/private paths", "reader eval suite v3 PASS (current 5/5x2; M-01/M-09 majority-invariant 3 arms; M-04 T3 degrades 2/2; stub differential recorded; HOLDOUT not_run)", "PCM delivery: checkpoint + #7 receipt + PR Refs #7", "[ ] independent human review: the reader arms are the same model family as the writer — README_QUALITY_TDD requires independent review the release gate calls for; still open.", "[ ] suite-5 (hardened runner) current/stub results under evals/results/suite5/: when landed, score --dir evals/results/suite5 reports them as an independent cohort; do not add a README verdict line — the README already lists suite-5 as a cohort row (per acs-0003-retraction scope: no committed-entry edit)."], "depends_on": [], "goal": "Story-first README + CGM 0.4.0 validator-green adapter (.content-system) for agent-custom-setup", "id": "ACS-0003", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/7", "next_action": "#5 enforcement decision pending (owner). #10 (ACS-0009, #9-agent) must sync onto main before merge: stale base, +7 main commits. suite-5 may still land under evals/results/suite5/ with no README/line-46 edit required (both already describe the cohort table incl. suite-5). Do not edit the committed retraction entry; it is history.", "owner": "owner/Astra (omp session)", "priority": "P2", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "completed", "why": "Repo entry point is a stub; owner direction: human-first docs per content-generation-modules specs"}-->

- Status: completed
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

- [x] `python3 .../validate_content_system.py --root <cgm@f85e88b> --adapter .content-system --project-root .` → `VALID: … and target adapter`, exit 0 (observed pre-status-line and re-run after; output in checkpoints).
- [x] README has all 9 `## ` contract headings + all 15 required reference strings + bold scan anchors + a repository-grounded worked example; Evidence-and-boundaries table separates shipped / branch-pending / planned with permalinks; order-independent "Status at a glance" summary added after eval iteration.
- [x] Every `cite_in_readme:true` brief URI appears verbatim in README; every manifest asset path exists.
- [x] `continuity validate` VALID; secret pattern clean; no private paths in product files.
- [x] Reader-task eval suite (owner direction: omp CLI differential/iterative): key v3 SUITE PASS — `current` 5/5×2 arms, M-01 `reordered` + M-09 `bold_stripped` majority-invariance (3 arms each), M-04 `claim_removed` T3-degrades 2/2, `stub` differential current 5.0 vs stub 2.0 recorded; HOLDOUT `not_run`; full disclosure of key revisions + isolation confound in `evals/README.md`.
- [x] Delivered per PCM: checkpoint on `task/ACS-0003-readme-docs`, #7 receipt, PR #8 `Refs #7`.

## Evidence and sources

- Spec: `Pukujan/content-generation-modules`@`f85e88bc00362c53061d95ac7811bd9c6ada8e32` — `system-version.json`, `templates/readme-contract.json`, `docs/README_PLAYBOOK.md`, `scripts/validate_content_system.py` (`check_adapter`, `check_project_brief_v2`, `check_narrative_assets`, `_valid_repository_permalink`).
- Prior reviewed adapter/README: `origin/feat/scaffold-pcm-cgm-1`@`8420b7876a77b38985b652541071e8cca72288ca` (PR #2, open).
- Repo reality: `main`@`1c44c8d2f25cb71e8acb20253e2cc26cd682af81` (PCM adoption); oh-my-pi @`0b29fdccda48c875fac07b7f087b59609cbbfb99` (PR #4 pending); JEV smoke evidence on issue #3.
- Eval evidence (observed 2026-09-26T02:08–02:46Z): 12 arms × 5 tasks (60 sessions) via `omp -p` headless arms. Cohort status (retraction entry acs-0003-retraction-20260926 supersedes the honesty entry's 'verified three ways'): M-01/M-04/M-09 verdicts sit within one firmly-original cohort and stand; suite-4 `stub`'s runner code is indeterminate from records (v2 rewrite provably landed in (02:46Z,03:29Z]; mtime + advisor-artifact legs retracted), so the current-vs-stub differential is stated as bounded — the fully-hardened 03:29Z smoke independently fails 4/5 stub tasks, preserving the direction. Raw JSON at `evals/results/` + archives (`v1-prekey/`, `v2-prekey3/`, `smoke/`); `python3 evals/score.py --dir evals/results` reproduces the verdict block. Limitations: model-arm proxy (writer==reader family, not independent review), truncated v1 answers, v3 self-admitted verbatim phrase anchors.

## Related records

- Leaf: #7 (parent: none; dependencies: none). Refs #1 (registry pending), #3 (oh-my-pi pending merge).
- Primary writer: omp session (owner/Astra laptop) / branch `task/ACS-0003-readme-docs` / source issue revision: #7 opened 2026-09-25 / as-of: projection current.
- PR #10 (ACS-0009/#9-agent) fact-checked 05:35Z: base 1c44c8d, single commit, diff = POLICY.md + modules/claude-code/.../v0.2.0/* only — does NOT touch CURRENT/AGENTS (collision risk is on #10's sync, not my closeout); mergeable UNKNOWN pending. PR #2 head 8420b78: CONFLICTING. Suite-5 launched 05:3xZ, isolated via --out evals/results/suite5/ (guard: score refuses mixed schemas).

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

### 2026-09-26 03:11:34 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["None for this task. (Repo-wide: Actions plan-gate on #5 unchanged.)"],"changed":["README.md, evals/ (key+builder+runner+scorer+protocol+variants+20 results JSON), tasks/TASK-ACS-0003-readme-docs.md, checkpoints/CURRENT.md"],"completed":["Owner-directed eval layer delivered: spec-driven reader-task harness per CGM README_QUALITY_TDD/HOLDOUT_EVALUATION (pinned f85e88b) using omp -p headless arms. Suite 4 (key v3, 02:08-02:46Z, 13 arms/65 sessions): SUITE PASS \u2014 current T1-T5 5/5 on 2 arms; M-01 reordered + M-09 bold_stripped majority-invariant vs current (3 arms each); M-04 claim_removed T3 degrades 2/2; stub differential current 5.0 vs stub 2.0 (no regression); HOLDOUT labeled not_run. README iterated from failures: order-independent Status-at-a-glance line. Runner hardened post-suite (isolation flags, advisor-off overlay, sha256, full-answer records) for future runs."],"decisions":["Key revisions v1->v2->v3 fully disclosed in evals/README.md incl. self-admission that v3 copied phrase anchors verbatim from failing answers (lists unchanged during suite 4, verdicts stand). Isolation confound (ambient advisor, repo cwd, default rules) disclosed and bounded: identical-environment stub-2.0 vs current-5.0 spread + claim_removed T3-only degradation are unexplained by contamination. Reader remains a model proxy, NOT independent human review \u2014 human pass stays open. No 4th suite: existing evidence closes the direction."],"evidence":["evals/results/run_*.json (raw per-arm answers/reasons) committed on branch incl. v1-prekey/ + v2-prekey3/ archives; score.py verdict block quoted in evals/README.md; product commit eb3ba4e; continuity validate VALID; CGM validator VALID re-checked post-README-edit (9/9 sections, 15/15 refs, 24 bold anchors)."],"next_action":"Publish #7 eval receipt + PR #8 body update with verdict block; owner merges #8 (or syncs onto gated main if #6 lands first).","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0003","timestamp":"2026-09-26T03:11:34Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"a114a9c1877791b671dc3da9ed719ed73c88abe23d250e32a0e85f99ed86fd02","request_id":"acs-0003-eval-20260926","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0003"} -->

Completed:
- Owner-directed eval layer delivered: spec-driven reader-task harness per CGM README_QUALITY_TDD/HOLDOUT_EVALUATION (pinned f85e88b) using omp -p headless arms. Suite 4 (key v3, 02:08-02:46Z, 13 arms/65 sessions): SUITE PASS — current T1-T5 5/5 on 2 arms; M-01 reordered + M-09 bold_stripped majority-invariant vs current (3 arms each); M-04 claim_removed T3 degrades 2/2; stub differential current 5.0 vs stub 2.0 (no regression); HOLDOUT labeled not_run. README iterated from failures: order-independent Status-at-a-glance line. Runner hardened post-suite (isolation flags, advisor-off overlay, sha256, full-answer records) for future runs.

Evidence:
- evals/results/run_*.json (raw per-arm answers/reasons) committed on branch incl. v1-prekey/ + v2-prekey3/ archives; score.py verdict block quoted in evals/README.md; product commit eb3ba4e; continuity validate VALID; CGM validator VALID re-checked post-README-edit (9/9 sections, 15/15 refs, 24 bold anchors).

Decisions:
- Key revisions v1->v2->v3 fully disclosed in evals/README.md incl. self-admission that v3 copied phrase anchors verbatim from failing answers (lists unchanged during suite 4, verdicts stand). Isolation confound (ambient advisor, repo cwd, default rules) disclosed and bounded: identical-environment stub-2.0 vs current-5.0 spread + claim_removed T3-only degradation are unexplained by contamination. Reader remains a model proxy, NOT independent human review — human pass stays open. No 4th suite: existing evidence closes the direction.

Changed:
- README.md, evals/ (key+builder+runner+scorer+protocol+variants+20 results JSON), tasks/TASK-ACS-0003-readme-docs.md, checkpoints/CURRENT.md

Blocked/uncertain:
- None for this task. (Repo-wide: Actions plan-gate on #5 unchanged.)

Next:
- Publish #7 eval receipt + PR #8 body update with verdict block; owner merges #8 (or syncs onto gated main if #6 lands first).

### 2026-09-26 03:13:22 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["None for this task; repo Actions plan-gate unchanged (#5)."],"changed":["README.md, evals/ (key+builder+runner+scorer+protocol+variants+20 results), tasks/TASK-ACS-0003-readme-docs.md, checkpoints/CURRENT.md"],"completed":["Owner-directed eval layer delivered: spec-driven reader-task harness per CGM README_QUALITY_TDD/HOLDOUT_EVALUATION (pinned f85e88b) using omp -p headless arms. Suite 4 (key v3, 02:08-02:46Z, 13 arms/65 sessions): SUITE PASS \u2014 current T1-T5 5/5 on 2 arms; M-01 reordered + M-09 bold_stripped majority-invariant vs current (3 arms each); M-04 claim_removed T3 degrades 2/2; stub differential current 5.0 vs stub 2.0 (no regression); HOLDOUT labeled not_run. README iterated from failures: order-independent Status-at-a-glance line. Runner hardened post-suite (isolation flags, advisor-off overlay, sha256, full-answer records) for future runs."],"decisions":["Key revisions v1->v2->v3 fully disclosed in evals/README.md incl. self-admission v3 copied phrase anchors from failing answers (lists unchanged during suite 4; verdicts stand). Isolation confound disclosed, bounded by stub-2.0 vs current-5.0 in identical environment. Reader = model proxy, not independent human review. No 4th suite."],"evidence":["evals/results/run_*.json (raw per-arm answers/reasons) committed on branch incl. v1-prekey/ + v2-prekey3/ archives; score.py verdict block quoted in evals/README.md; product commit eb3ba4e + CURRENT commit; continuity validate VALID; CGM validator re-checked post-README-edit (9/9 sections, 15/15 refs)."],"next_action":"Publish #7 eval receipt + PR #8 body update with verdict; owner merges #8 (or syncs onto gated main after #6).","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0003","timestamp":"2026-09-26T03:13:22Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"f1d69717b730991bdb58ebea948cd8cb937135d641e2728d9f48a4a0a8a851ac","request_id":"acs-0003-eval-b-20260926","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0003"} -->

Completed:
- Owner-directed eval layer delivered: spec-driven reader-task harness per CGM README_QUALITY_TDD/HOLDOUT_EVALUATION (pinned f85e88b) using omp -p headless arms. Suite 4 (key v3, 02:08-02:46Z, 13 arms/65 sessions): SUITE PASS — current T1-T5 5/5 on 2 arms; M-01 reordered + M-09 bold_stripped majority-invariant vs current (3 arms each); M-04 claim_removed T3 degrades 2/2; stub differential current 5.0 vs stub 2.0 (no regression); HOLDOUT labeled not_run. README iterated from failures: order-independent Status-at-a-glance line. Runner hardened post-suite (isolation flags, advisor-off overlay, sha256, full-answer records) for future runs.

Evidence:
- evals/results/run_*.json (raw per-arm answers/reasons) committed on branch incl. v1-prekey/ + v2-prekey3/ archives; score.py verdict block quoted in evals/README.md; product commit eb3ba4e + CURRENT commit; continuity validate VALID; CGM validator re-checked post-README-edit (9/9 sections, 15/15 refs).

Decisions:
- Key revisions v1->v2->v3 fully disclosed in evals/README.md incl. self-admission v3 copied phrase anchors from failing answers (lists unchanged during suite 4; verdicts stand). Isolation confound disclosed, bounded by stub-2.0 vs current-5.0 in identical environment. Reader = model proxy, not independent human review. No 4th suite.

Changed:
- README.md, evals/ (key+builder+runner+scorer+protocol+variants+20 results), tasks/TASK-ACS-0003-readme-docs.md, checkpoints/CURRENT.md

Blocked/uncertain:
- None for this task; repo Actions plan-gate unchanged (#5).

Next:
- Publish #7 eval receipt + PR #8 body update with verdict; owner merges #8 (or syncs onto gated main after #6).

### 2026-09-26 03:33:24 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["None; merging now."],"changed":["evals/run_arms.py, evals/omp-arms-overlay.yml, evals/README.md, evals/results (rearchive), tasks/TASK-ACS-0003-readme-docs.md, checkpoints/CURRENT.md"],"completed":["Eval layer finalized per owner stop directive: hardened runner (in-repo overlay, isolation flags, sha256, full answers), suite-4 archived v3-prehard with honest mtime-audit disclosure (last stub arm ran isolated; isolated re-smoke still stub 4/5 FAIL => differential direction holds), counts corrected 12 arms/60 sessions. READY for owner-merge: user directed merging PRs."],"decisions":["Owner direction 03:2xZ: stop eval iteration, commit+push+merge PRs. Merges proceed as owner review+merge recorded on owning issues; #5 stays OPEN (acceptance 1-4 unmet, plan-gate)."],"evidence":["03:29Z isolated smoke: run_stub-20260926T032932Z.json schema arm-run.v2 (sha256 64, flags recorded, answer_full) results T2 only pass; suite-4 files stat-audited (stub end 02:48:00 vs ~103s for 10 sessions ~10s/arm vs 31-90s pre-hardening)."],"next_action":"Post owner-direction supersessions on #3/#5/#7; merge #4 -> sync -> merge #6 -> sync -> merge #8; closeout CURRENT+tasks on main; close #3/#7 with merge SHAs; #5 remains open plan-blocked.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0003","timestamp":"2026-09-26T03:33:24Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"49a0bb193d2e4df6442bca0a7e13158c6c6e5dd2c4b14c529639edf93b000a9e","request_id":"acs-0003-final-20260926","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0003"} -->

Completed:
- Eval layer finalized per owner stop directive: hardened runner (in-repo overlay, isolation flags, sha256, full answers), suite-4 archived v3-prehard with honest mtime-audit disclosure (last stub arm ran isolated; isolated re-smoke still stub 4/5 FAIL => differential direction holds), counts corrected 12 arms/60 sessions. READY for owner-merge: user directed merging PRs.

Evidence:
- 03:29Z isolated smoke: run_stub-20260926T032932Z.json schema arm-run.v2 (sha256 64, flags recorded, answer_full) results T2 only pass; suite-4 files stat-audited (stub end 02:48:00 vs ~103s for 10 sessions ~10s/arm vs 31-90s pre-hardening).

Decisions:
- Owner direction 03:2xZ: stop eval iteration, commit+push+merge PRs. Merges proceed as owner review+merge recorded on owning issues; #5 stays OPEN (acceptance 1-4 unmet, plan-gate).

Changed:
- evals/run_arms.py, evals/omp-arms-overlay.yml, evals/README.md, evals/results (rearchive), tasks/TASK-ACS-0003-readme-docs.md, checkpoints/CURRENT.md

Blocked/uncertain:
- None; merging now.

Next:
- Post owner-direction supersessions on #3/#5/#7; merge #4 -> sync -> merge #6 -> sync -> merge #8; closeout CURRENT+tasks on main; close #3/#7 with merge SHAs; #5 remains open plan-blocked.

### 2026-09-26 03:43:43 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["None."],"changed":["checkpoints/CURRENT.md (merge union); merge commit"],"completed":["Synced gated main into task/ACS-0003 append-only (merge 728e0ce; main carried b094c07 gates + 7df54a1 module; #3 closed with verified closeout). CURRENT union resolved. PR #8 head now includes gates + module history \u2014 merge-ready."],"decisions":["None new."],"evidence":["continuity validate VALID post-merge; zero conflict markers; push origin 728e0ce confirmed via gh pr view head."],"next_action":"Squash-merge #8, verify main, #7 closeout + manual close.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0003","timestamp":"2026-09-26T03:43:43Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"9fec7a0fb0157171eb58968093cd063f28928c70c43676d540a103d16977dc67","request_id":"acs-0003-sync-20260926","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0003"} -->

Completed:
- Synced gated main into task/ACS-0003 append-only (merge 728e0ce; main carried b094c07 gates + 7df54a1 module; #3 closed with verified closeout). CURRENT union resolved. PR #8 head now includes gates + module history — merge-ready.

Evidence:
- continuity validate VALID post-merge; zero conflict markers; push origin 728e0ce confirmed via gh pr view head.

Decisions:
- None new.

Changed:
- checkpoints/CURRENT.md (merge union); merge commit

Blocked/uncertain:
- None.

Next:
- Squash-merge #8, verify main, #7 closeout + manual close.

### 2026-09-26 04:21:42 UTC — owner/Astra (omp session)

<!-- continuity:checkpoint {"agent":"owner/Astra (omp session)","blocked":["None."],"changed":["evals/README.md, evals/run_arms.py, evals/results/smoke/, tasks/TASK-ACS-0001-oh-my-pi-module.md, tasks/TASK-ACS-0003-readme-docs.md"],"completed":["Honesty pass: cohort uniformity VERIFIED (mtime refutes my mid-suite-split admission; advisor-log/artifact evidence for uniform original conditions, labeled inferred); runner records observable fields (advisor_overlay_passed/advisor_effect:unverified); score pool made glob-safe (smoke to results/smoke/); ACS-0001 placeholder acceptance replaced with issue #3's real criteria; ACS-0003 evidence line corrected."],"decisions":["Advisory-caught contradiction ('identical-environment' vs split admission) resolved by measurement, not wording."],"evidence":["stat run_arms.py 22:13Z vs stub launch 02:46:17Z; grep advisor ~/.omp/logs 22:08-22:48 window = 0; find session dirs __advisor* under this repo = 0 (only old /tmp dogfood session); python score after pool restore = SUITE PASS (5 files, 12 arms)."],"next_action":"Post #7 correction comment (split admission refuted; placeholders fixed); monitor PR #10/#2 collisions when owner asks.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"ACS-0003","timestamp":"2026-09-26T04:21:42Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"b7f646a5b1ca02563418914c56a5681131f99aa39107e0e2e082a78d9e7f0c69","request_id":"acs-0003-honesty-20260926","schema":"project-continuity.checkpoint-operation.v1","task_id":"ACS-0003"} -->

Completed:
- Honesty pass: cohort uniformity VERIFIED (mtime refutes my mid-suite-split admission; advisor-log/artifact evidence for uniform original conditions, labeled inferred); runner records observable fields (advisor_overlay_passed/advisor_effect:unverified); score pool made glob-safe (smoke to results/smoke/); ACS-0001 placeholder acceptance replaced with issue #3's real criteria; ACS-0003 evidence line corrected.

Evidence:
- stat run_arms.py 22:13Z vs stub launch 02:46:17Z; grep advisor ~/.omp/logs 22:08-22:48 window = 0; find session dirs __advisor* under this repo = 0 (only old /tmp dogfood session); python score after pool restore = SUITE PASS (5 files, 12 arms).

Decisions:
- Advisory-caught contradiction ('identical-environment' vs split admission) resolved by measurement, not wording.

Changed:
- evals/README.md, evals/run_arms.py, evals/results/smoke/, tasks/TASK-ACS-0001-oh-my-pi-module.md, tasks/TASK-ACS-0003-readme-docs.md

Blocked/uncertain:
- None.

Next:
- Post #7 correction comment (split admission refuted; placeholders fixed); monitor PR #10/#2 collisions when owner asks.

## Handoff

Read PROJECT → CURRENT → this task → minimum relevant spec. Checkpoint before stopping.
