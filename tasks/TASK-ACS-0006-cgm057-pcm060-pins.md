# TASK-ACS-0006 — CGM 0.5.7 + PCM 0.6.0 Pin Sync and README Visuals

<!-- continuity:task {"acceptance": ["adapter .content-system/system-version.json pins helper 0.5.7 at c069613ca8b3e02bcf5aba1960160583537f8a3a and validate_content_system.py reports helper+adapter VALID and writing mode OK", "root README carries two narrative rasters (accepted hero + text-free three-module visual) with full provenance in asset-manifest.json and a module-separation filename legend", ".github/workflows/ci.yml PCM_PIN bumped to 4e2385474b4af9249ca009cbdcb38c4498932475 (CLI 0.6.0) and continuity validate+preflight pass on a clean clone at that pin", "AGENTS.md hotload sentence and project-brief.json evidence agree with the 0.5.7 / 0.6.0 eight-module reality", "PCM delivery: checkpoint + #19/#44 receipts + PR Refs #19 #44"], "depends_on": [], "goal": "Bring the ACS adopter surface to the current helper pins: bump the content-system adapter from CGM 0.5.5 to 0.5.7, correct the stale PCM CI pin from 0.5.0 to 0.6.0, ship CGM-spec narrative README visuals replacing the SVG-only text-first boundary, and record the merge receipts on the owning issues.", "id": "ACS-0006", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/19", "next_action": "None for ACS-0006 — PR #45 merged at 5bb85de, receipts posted on #19 (closed) #44 #46 #11, CURRENT.md synced. Physical module split continues on #44; pin-manifest automation on #46; live session-ops receipt on #22.", "owner": "owner/Astra (omp session)", "priority": "P1", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "completed", "why": "Owner reported the regenerated README still showed the old SVG seal and no narrative visuals, and asked to update the CGM and PCM adapters to the current versions; the CI PCM pin (743d50e = CLI 0.5.0) and the adapter pin (0.5.5) had silently drifted behind the hotload module's own 0.5.7 / 0.6.0 pins."} -->

- Status: completed
- Owner / primary writer: owner/Astra (omp session)
- Priority: P1
- Depends on: none
- Leaf owning issue: [#19](https://github.com/Pukujan/agent-custom-setup/issues/19)
- Parent ancestry: #19 (README regeneration); related: [#44](https://github.com/Pukujan/agent-custom-setup/issues/44) (module separation), [#15](https://github.com/Pukujan/agent-custom-setup/issues/15), [#17](https://github.com/Pukujan/agent-custom-setup/issues/17), [#22](https://github.com/Pukujan/agent-custom-setup/issues/22)
- Branch: `task/ACS-0006-cgm057-pcm060-pins`

## Goal

Bring the ACS adopter surface onto the current helper pins and give the regenerated README the CGM-spec visuals the owner asked for:

- Adapter `.content-system/system-version.json`: CGM 0.5.5 → **0.5.7** @ `c069613…`.
- CI `.github/workflows/ci.yml` `PCM_PIN`: `743d50e…` (CLI 0.5.0) → `4e23854…` (CLI 0.6.0), matching the hotload module.
- Root README: replace the SVG-only text-first boundary with the accepted narrative hero plus a new text-free three-module overview raster, both with full manifest provenance.
- Sync `AGENTS.md`, `assets/IMAGE_NOTES.md`, and `project-brief.json` evidence to that reality.

## Why

Owner report 2026-10-01: the regenerated README still rendered the old compact SVG seal and no narrative visuals, and the CGM/PCM adapters were behind. Investigation confirmed the CI PCM pin (0.5.0) and the adapter pin (0.5.5) had silently drifted from the hotload module's own 0.5.7 / 0.6.0 pins.

## Allowed files

- `.content-system/{system-version,brand-language,asset-manifest,visual-style,project-brief}.json`, `.content-system/filename-legends/module-separation.json` (new)
- `README.md`, `AGENTS.md`, `assets/acs-three-modules.jpg` (new), `assets/acs-three-modules-prompt.md` (new), `assets/IMAGE_NOTES.md`
- `.github/workflows/ci.yml` (PCM_PIN only)
- `checkpoints/CURRENT.md`, `tasks/TASK-ACS-0006-*.md` (this record)

## Non-goals

- No directory moves for the three modules (that is #44's scope).
- No change to the hotload module's own pins (already 0.5.7 / 0.6.0).
- No vendoring of PCM/CGM source.

## Evidence

- CGM `origin/main` = `c069613` (0.5.7); PCM `origin/main` = `465036a` (CLI 0.6.0); pin `4e23854` is also CLI 0.6.0.
- `validate_content_system.py` at `c069613`: helper+adapter **VALID**, writing mode **OK** (recorded on #19).
- `continuity` 0.6.0 @ `4e23854`: `validate` **VALID** + `preflight` **TARGET_VALID** on a clean clone of main.
- `gate.py --fixture block_selfhost_despite_hosted_brief.json --judge mock --json` → `"decision": "deny"`; jev-gate-pin suite 16 passed.

## Next atomic action

Open the PR (Refs #19 #44), wait for green `gates`, merge, append the leaf receipts on #19 and #44, and sync `checkpoints/CURRENT.md` to the merged SHA.

## Checkpoint log

### 2026-10-01 — pin sync + visuals increment (as-of; live issues own progression)

Completed:
- Adapter pins CGM 0.5.7 @ `c069613…` (was 0.5.5 @ `085aeb1…`); brand-language + project-brief evidence synced; stale "planned/supersedes PR #20" item rewritten to shipped reality.
- CI `PCM_PIN` bumped `743d50e…` (CLI 0.5.0) → `4e23854…` (CLI 0.6.0), matching `hotload_check.py`'s pin; proven locally: continuity 0.6.0 `validate` VALID + `preflight` TARGET_VALID on a clean clone of main.
- README restructured twice per owner direction: first three-module split, then **hotloader-first** — the multi-agent hotloader is the main marketing/user-facing feature; `jev-omp` + `jev-benchmark` pivot to supporting sections. Two narrative rasters ship (accepted hero + new text-free three-module visual `assets/acs-three-modules.jpg`, attempt 1 rejected for garbled lettering); provenance in `asset-manifest.json` + `filename-legends/module-separation.json`; `IMAGE_NOTES.md` no longer points at the removed image-generation section.
- `AGENTS.md` hotload sentence synced to FULL CGM 0.5.7 / eight modules (was 0.5.1 / seven); `registry.json` hotloader projection synced 0.5.1 @ `9874b26` → 0.5.7 @ `c069613` / eight modules; `hotload_check.py` "seven" error strings → eight with threshold from `REQUIRED_CGM_MODULES`; removed the self-contradictory 0.5.4/c95d73a pin assertion in `test_hotload_check.py` (heading test now defers to `test_cgm_pin_constants_057`).

Evidence:
- `validate_content_system.py` @ `c069613`: helper+adapter **VALID**; `--mode writing` **VALID**.
- `gate.py --fixture block_selfhost… --judge mock --json` → `"decision": "deny"`; jev-gate-pin tests 16 passed; hotload suite 15 passed / 2 skipped (was 1 failed on `main`).
- Pin-drift audit recorded as issue #46 (proposal: single `pins.json` + generator + fail-closed drift check in `gates`); hotloader already points adopters at 0.5.7/0.6.0, five projections had drifted and are corrected here.

Decisions:
- Keep pins as reviewed commits (no silent `main`-following) per HOTLOAD.md binding rule; "automatic" updates deferred to issue #46's manifest design.
- Second README visual ships text-free because the image model garbled in-image lettering; exact title/subtitle carried by adjacent prose + manifest fields per IMAGE_GUIDE rejection rules.
- CI PCM pin set to `4e23854` (CLI 0.6.0, the hotload module's own pin) rather than moving `main` `465036a`, to keep the required check aligned with what adopters must pin.

Blocked/uncertain: none for this increment; live issue states (#19/#44/#46) own progression beyond the merge.

Next: green `gates` on PR #45 → merge → receipts on #19/#44/#46/#11 → sync CURRENT.md.

### 2026-10-01 — regenerated visuals + hotloader-first art (as-of; live issues own progression)

Completed:
- Owner added the `xai-oauth/grok-imagine-image` model to the image role; regenerated both README rasters with it: `assets/acs-readme-hero.png` (2816x1584; exact title/subtitle legible on first pass) and a new hub-and-spoke `assets/acs-three-modules.png` where the multi-agent hotloader card is dominant/central and `jev-omp` + `jev-benchmark` are smaller satellites — matching the README's hotloader-first framing. Old flux-era `.jpg` removed.
- Manifest, visual-style, filename legend, IMAGE_NOTES, README alt text, and project-brief evidence synced to the regenerated assets (new SHA-256 hashes, review notes, prompt records).

Evidence:
- Visual inspection of both PNGs before acceptance (hero panel text spelled correctly at full size; module map has zero lettering).
- `validate_content_system.py` @ `c069613` re-run after edits (helper+adapter VALID recorded below).

Changed: `assets/acs-readme-hero.png` (new), `assets/acs-readme-hero-prompt.md` (new), `assets/acs-three-modules.png` (regenerated), `assets/acs-three-modules.jpg` (deleted), `assets/acs-three-modules-prompt.md`, `assets/IMAGE_NOTES.md`, `README.md`, `.content-system/{asset-manifest,visual-style,project-brief}.json`, `.content-system/filename-legends/module-separation.json`.

Decisions:
- Keep `jev-routing-hero.png` for the product HTML page; only the root README swaps to the regenerated hero.
- Module map stays text-free; names carried by alt text + adjacent prose (IMAGE_GUIDE).

Blocked/uncertain: none.

Next: green `gates` on the updated PR #45 head → merge → receipts on #19/#44/#46/#11 → sync CURRENT.md.
