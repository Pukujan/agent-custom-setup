# TASK-ACS-0007 — CGM 0.5.12 Pin Move (hotload pack + adapter projections)

<!-- continuity:task {"acceptance": ["modules/coordination/multi-agent-hotload/v0.1.0/pins.json pins cgm.version 0.5.12 at 6831f91e165b62d719c05eb492f7375fa932b560 with 0.5.7 / c069613 recorded under superseded", "check_pins.py exits OK with every declared projection agreeing; hotload pack tests pass (23 passed)", "PROMPT_INJECT.md regenerated from CGM 0.5.12 docs/writing-routing.json via hotload_check.py --cgm-root", "no live ACS file still advertises 0.5.7 / c069613 as the current pin (projections, adapter .content-system, root README)", "PCM delivery: checkpoint + #55 receipt + PR Refs #55 (parent #52)"], "depends_on": [], "goal": "Move the multi-agent-hotload pack's pinned CGM from 0.5.7 to 0.5.12 in place so the certified {CGM 0.5.12, ACS 0.1.0} set is coherent, and carry every projection plus the live adapter/README surfaces with it.", "id": "ACS-0007", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/55", "next_action": "Open the PR (Refs #55, parent #52), wait for green gates, merge, post the #55 receipt and the #52 parent update, then remove the ACS-0052 worktree.", "owner": "owner/Astra (omp session)", "priority": "P1", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "active", "why": "The release train re-certified CGM at 0.5.12 (agent-stack-train #3/#4) and certifies ACS 0.1.0. Because this pack hard-pins CGM, the certified set {CGM 0.5.12, ACS 0.1.0} is internally false until the pack moves: ACS 0.1.0 would otherwise still install CGM 0.5.7, whose adopter-README contract predates the PNG-hero rule that OIO's CI now needs to enforce."} -->

- Status: active
- Owner / primary writer: owner/Astra (omp session)
- Priority: P1
- Depends on: none
- Leaf owning issue: [#55](https://github.com/Pukujan/agent-custom-setup/issues/55)
- Parent ancestry: [#52](https://github.com/Pukujan/agent-custom-setup/issues/52) (decouple coordination governance / adopt release-train manifest)
- Branch: `task/ACS-0052-cgm-0512-pin`

## Goal

Move the pack's CGM pin to the version the release train now certifies, in place
(module stays `v0.1.0`, matching the prior in-place CGM bump `895ae43`):

- `pins.json`: `cgm.version` 0.5.7 → **0.5.12**, `cgm.commit` →
  `6831f91e165b62d719c05eb492f7375fa932b560`; add `0.5.7` / `c069613` to
  `superseded`.
- Every declared projection moves with it (`AGENTS.md`, `registry.json`,
  `.content-system/system-version.json`, `.content-system/review-rubric.json`,
  and the pack's `BEHAVIOR.md`, `HOTLOAD.md`, `NOTES.md`, `PROMPT_INJECT.md`,
  `README.md`, `ROLES.md`, `module.json`, `examples/assignment.example.json`,
  `scripts/hotload_check.py`, `tests/test_hotload_check.py`).
- Regenerate `PROMPT_INJECT.md` from CGM 0.5.12's `docs/writing-routing.json`.

## Why

The release train re-certified CGM at 0.5.12 and certifies ACS `0.1.0`. Because
this pack hard-pins CGM, the certified set `{CGM 0.5.12, ACS 0.1.0}` is
internally false until the pack moves — ACS `0.1.0` would still install CGM
`0.5.7`. This is the ACS half of the owner-authorized CGM pin move (parent #52).

## Allowed files

- `modules/coordination/multi-agent-hotload/v0.1.0/**` (pins.json, projections,
  pin constants, pack tests)
- `AGENTS.md`, `registry.json`, `README.md`
- `.content-system/{system-version,review-rubric,asset-manifest,brand-language,project-brief}.json`
- `checkpoints/CURRENT.md`, `tasks/TASK-ACS-0007-*.md` (this record)

## Non-goals

- No change to the PCM pin (still CLI 0.6.0 @ `4e23854…`).
- No module version bump; the pack stays `v0.1.0`.
- No directory moves (that is #44's scope) and no PCM/CGM source vendoring.

## Evidence

- CGM `origin/main` HEAD is exactly `6831f91e…` (0.5.12); `system-version.json`
  there declares `"version": "0.5.12"` with the eight-module list.
- `check_pins.py` → `check_pins: OK (15 projections agree with pins.json)`.
- Hotload pack tests → `23 passed`.
- `hotload_check.py --cgm-root <CGM 0.5.12> --adopter-root .` regenerates
  `PROMPT_INJECT.md` with the new `reader_facing_explanations` route.
- CGM validator: helper+adapter **VALID** on the moved adapter.

## Deviations from the plan

- The plan listed the 15 checker-enforced projections. Four further files carried
  the old pin **outside** the checker's scan and were moved too, so no live ACS
  surface still advertises 0.5.7: `.content-system/asset-manifest.json`
  (`system_version`), `.content-system/brand-language.json`,
  `.content-system/project-brief.json` (solution line + pin evidence item), and
  the root `README.md` (full-stack wiring, evidence table, try-it comment).
- `tests/test_check_pins.py` hardcoded the old pin literals in two negative
  tests; after the bump those `str.replace` calls became no-ops and both tests
  failed. Updated to the new literals (`6831f91e…`, `0.5.12`).

## Next atomic action

Open the PR (Refs #55, parent #52), wait for green `gates`, merge, post the #55
receipt and the #52 parent update, then remove the ACS-0052 worktree.

## Checkpoint log

### 2026-10-02 — pin move to CGM 0.5.12 (as-of; live issues own progression)

Completed:
- `pins.json` moved to `cgm.version` 0.5.12 @ `6831f91e…`; `0.5.7` / `c069613`
  recorded under `superseded`. All 15 declared projections agree.
- `PROMPT_INJECT.md` regenerated from CGM 0.5.12's `docs/writing-routing.json`
  (adds the `reader_facing_explanations` route; `0.5.12` / `6831f91e`
  throughout).
- Four live surfaces outside the checker's scan moved: `asset-manifest.json`
  `system_version`, `brand-language.json`, `project-brief.json`, root `README.md`.
- `tests/test_check_pins.py`: two negative tests updated to the new pin literals.

Evidence:
- `check_pins.py` → `check_pins: OK (15 projections agree with pins.json)`.
- `pytest modules/coordination/multi-agent-hotload/v0.1.0/tests -q` → `23 passed`.
- CGM validator (0.5.12) helper+adapter → `VALID`.
- `hotload_check.py --cgm-root /d/claude/content-generation-modules --adopter-root .`
  → OK (PROMPT_INJECT regenerated).

Decisions:
- Move the pin in place and keep the module at `v0.1.0` rather than cutting a new
  module version — matches the prior in-place CGM bump (`895ae43`, 0.5.6→0.5.7)
  and keeps the certified ACS version stable at `0.1.0`.
- Move the four surfaces outside the checker's scan (`asset-manifest.json`
  `system_version`, `brand-language.json`, `project-brief.json`, root `README.md`)
  so no live ACS file still advertises 0.5.7; the checker cannot see them, so a
  green `check_pins` alone would have left the drift.
- Do **not** add `project-brief.json` to `pins.json` projections: its frozen
  evidence SHAs (`8c62ba1d…`, `999d870…`) and historical version strings would
  trip the commit/version scans, and those are provenance, not pins.
- Point the rewritten brief evidence item at the pin-move commit's tree
  (`8ff7e6b`) rather than the prior task's permalink (`6b02503`), which predated
  the version it claimed.

Blocked/uncertain:
- `continuity validate` reports 3 errors locally. Two ("task ACS-0002/ACS-0005
  is active but CURRENT.md active task is ACS-0004") pre-exist on `origin/main`
  and are absent from the pinned CI CLI `4e23854` (that check does not exist in
  it); the third ("additional worktree must be under pcm/worktree/<TASK-ID>") is
  the local-CLI `managed-worktrees` convention, invisible to CI, which checks
  out a single tree. None are CI blockers; recorded rather than "fixed" by
  editing unrelated task statuses.

Next: green `gates` on the PR → merge → #55 receipt + #52 parent update → remove
the ACS-0052 worktree.
