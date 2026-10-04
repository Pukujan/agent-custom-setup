# TASK-ACS-0009 — License the stack

<!-- continuity:task {"acceptance": ["ACS main carries LICENSE (FSL-1.1-ALv2), NOTICE, and TRADEMARK.md, and README links them", "check_pins.py exits OK, continuity validate is VALID, and the hotloader pack tests pass on the candidate", "the four pinned module repos (PCM, CGM, OIO, agent-stack-train) carry an Apache-2.0 LICENSE", "jev-dump is private", "PCM delivery: checkpoint + PR Refs #69"], "depends_on": [], "goal": "Stamp ACS with FSL-1.1-ALv2 (LICENSE, NOTICE, TRADEMARK.md, README license section) so third parties may legally run the hotload pack, and stamp the pinned module repos with Apache-2.0.", "id": "ACS-0009", "issue_url": "https://github.com/Pukujan/agent-custom-setup/issues/69", "next_action": "Commit the license files + README section, push the branch, open the PR (Refs #69), and confirm gates.", "owner": "owner/Pukujan ([CL] session)", "priority": "P1", "protocol_version": "0.1.0-draft", "schema": "project-continuity.task.v1", "status": "active", "why": "Owner direction 2026-10-04: license the stack so others can use but not copy or compete. Every public stack repo carried no license, so no third party had the legal right to run the pack (OIO #24)."} -->

- Status: active
- Owner / primary writer: owner/Pukujan ([CL] session)
- Priority: P1
- Depends on: none
- Leaf owning issue: [#69](https://github.com/Pukujan/agent-custom-setup/issues/69)
- Cross-repo observation: OIO [#24](https://github.com/Pukujan/observational-issue-ops/issues/24)
- Branch: `task/ACS-licensing`

## Goal

Give the stack an explicit license so third parties may legally use it. ACS itself
gets **FSL-1.1-ALv2** (use freely, including internal production; no competing
product or service; converts to Apache-2.0 on the second anniversary). The pinned
module repos get **Apache-2.0**. `jev-dump` goes private.

## Why

Every public stack repo shipped with **no license** (`gh api ... .license` → `null`
for ACS, PCM, CGM, OIO, agent-stack-train, jev-dump). No license means all rights
reserved: a third party has no legal right to run, modify, or redistribute the
code, even though GitHub's ToS grants view-and-fork. The owner intends to publish
a downloadable, productized ACS — that intent is legally unfulfillable without a
license.

## Allowed files

- `LICENSE`, `NOTICE`, `TRADEMARK.md`, `README.md`, `AGENTS.md`
- `tasks/TASK-ACS-0009-*.md`, `checkpoints/CURRENT.md`

## Non-goals

- No CLA machinery (the sole contributor already holds relicensing rights).
- No change to the PCM/CGM pins.
- No relicensing of third-party vendored content (ACS vendors none; PCM/CGM are
  pinned external dependencies).

## Evidence

- `gh api repos/Pukujan/<repo> --jq .license` → `null` for the six repos
  (observed 2026-10-04).
- FSL-1.1-ALv2 canonical text: `getsentry/fsl.software` (`FSL-1.1-ALv2.template.md`).
- ACS vendors nothing third-party (`find modules -type f` shows only pack docs,
  scripts, and tests).

## Next atomic action

Commit the license files + README section, push the branch, open the PR
(Refs #69), and confirm `gates`.

## Checkpoint log

### 2026-10-04 — ACS license stamp (as-of; live issues own progression)

Completed:
- Added `LICENSE` (FSL-1.1-ALv2, Copyright 2026 Pukujan), `NOTICE` (no vendored
  third-party source; PCM/CGM listed as pinned external deps), and `TRADEMARK.md`.
- Added a README `## License` section linking all three.

Evidence:
- `check_pins.py` OK (15 projections agree); hotloader pack tests pass
  (21 passed, 2 skipped); `continuity validate` VALID; `continuity preflight`
  TARGET_VALID.

Decisions:
- ACS = FSL-1.1-ALv2 (owner choice over PolyForm Shield); module repos = Apache-2.0.
- Licensor line names `Pukujan` (the GitHub identity); owner may substitute a
  legal entity later.

Blocked/uncertain:
- Module-repo licenses and `jev-dump` visibility are cross-repo steps handled
  outside this branch.

Next: commit, push, open the PR (Refs #69).
