# PROMPT_INJECT — acs_prompt_inject (CGM 0.5.7)

Generated / refreshed by `hotload_check` after full adapter `VALID`.
Source: CGM `docs/writing-routing.json` → `acs_prompt_inject` @ `c069613ca8b3e02bcf5aba1960160583537f8a3a`.

Also see: CGM [`docs/ACS_VERIFY.md`](https://github.com/Pukujan/content-generation-modules/blob/c069613ca8b3e02bcf5aba1960160583537f8a3a/docs/ACS_VERIFY.md) and [`docs/writing-routing.json`](https://github.com/Pukujan/content-generation-modules/blob/c069613ca8b3e02bcf5aba1960160583537f8a3a/docs/writing-routing.json).

**Pin:** CGM `0.5.7` @ `c069613ca8b3e02bcf5aba1960160583537f8a3a` (main). After any future CGM merge that moves the tip, re-pin ACS hotload to the new main SHA.

## application

`must_load` — agents MUST load the listed module before writing each surface.

## When

At agent start / session boot for EVERY repo that pins CGM — not per-report and not ACS-only. Paste system_block into the agent system prompt before the agent writes ANY human-facing deliverable: GitHub or docs prose, HTML reports, compare HTML/UIs, appendable HTML, posts, papers, or other agent-produced human-readable artifacts — and before naming generated artifact / asset-manifest / media paths.

## human_facing_default

- **load:** `human-sounding-writing` (**hsw**) — `required_load: true`, `default_on: true`
- **covers:** `every human-facing task/output`, `HTML reports`, `compare HTML`, `compare UIs`, `agent-produced human-readable HTML`, `agent-produced human-readable artifacts with prose`, `GitHub and docs prose`, `posts blogs social`, `papers and data writeups`
- **exceptions:** `readme_product_entry`, `generated_artifact_filenames` (README/product → writing-direction; basenames → **hon**)
- **rule:** HSW is ON by default for EVERY human-facing task/output including HTML reports, compare HTML/UIs, and appendable HTML. Not optional. Not per-report opt-in. Visible HTML prose → **hsw**; filesystem basenames → **hon**.

## Boot paste — acs_prompt_inject.system_block (ALWAYS-ON)

- **always_on:** `true`
- **opt_in_forbidden:** `true`
- **rule:** Paste the block below into the agent **system prompt at session boot** (every CGM adopter). Not per-report. Not per-HTML. Not ACS-only.

```
CGM ALWAYS-ON WRITING RULE (every adopter that pins this helper)

Before you write ANY human-facing output — including HTML reports, compare HTML/UIs, appendable HTML, PR/issue/commit prose, docs, posts, papers, or other readable artifacts — you MUST load and apply modules/human-sounding-writing/SKILL.md (hsw).

This rule is always on. Opt-in is forbidden. Do not wait for a per-task, per-report, or per-HTML flag.

Exceptions (only these):
- README.md / product entry pages → load modules/writing-direction/SKILL.md instead
- Generated artifact filenames / asset-manifest paths / media basenames / filename legends → load modules/human-output-naming/SKILL.md (hon) for basenames; visible prose inside HTML still uses hsw

HTML reports, compare HTML, and compare UIs have NO skip path. An exception reason is not allowed for those surfaces.

If you cannot load the skill file from the pinned CGM checkout, stop and report that — do not draft jargon-heavy or tool-dump HTML instead.

Filenames: use scripts/human_filename (speakable basenames; optional safe_twin) and keep a per-feature legend. Hash may stay a separate manifest field.
```

## Instruction (MUST paste/apply into system or task prompts)

ALWAYS-ON for every CGM adopter (ACS is one consumer, not the only one). Paste acs_prompt_inject.system_block into the agent system prompt at start. HSW (human-sounding-writing) is ON by default for EVERY human-facing task/output. Before writing ANY human-facing output (including HTML/compare), MUST load modules/human-sounding-writing/SKILL.md. Opt-in is forbidden; always_on is true. Skipping requires an explicit machine-readable exception reason that is NOT allowed for HTML reports, compare HTML, or compare UIs. README and product entry pages → writing-direction. Pull request titles/bodies, issue titles/bodies, issue-log titles, commit messages, commit subjects, non-README docs, changelog prose, posts/blogs/social/general prose, papers/data writeups, HTML reports, compare HTML, compare UIs, appendable HTML reports, and other agent-produced human-readable HTML → human-sounding-writing (hsw). Soft enforcement means no NLP CI grade of prose; the contract language is MUST/APPLY/default_on/always_on, not prefer. Follow apply_checklist and human_facing_default in this file. Generated artifact filenames, asset-manifest paths, committed media basenames, and filename legends → human-output-naming (hon): MUST load that skill and use scripts/human_filename with speakable basenames (omit defaults; optional safe_twin); keep a per-feature legend (glossary + file list); never opaque p0/hex stems or robot key=value stems. Prose and visible text inside HTML still use hsw; basenames use hon.

## apply_checklist

1. Identify the writing surface (README, PR title/body, issue title/body, issue-log title, commit message/subject, non-README doc, changelog prose, post/blog/social, paper/data writeup, HTML report, compare HTML/UI, or other human-facing HTML/artifact).
2. Look up the surface in routes[].surfaces in docs/writing-routing.json (or the table in docs/WRITING_ROUTING.md). If it is human-facing and not README/product entry and not a filename-only surface, default to human-sounding-writing (human_facing_default).
3. MUST load modules/<load>/SKILL.md for that route before drafting — required_load is true; do not skip because the surface is short, 'just a commit', or 'just an HTML report'.
4. Apply the module rules to the draft (voice, AI-tell scrub, bold policy as the module states).
5. README / product entry stays on writing-direction; do not apply hsw bold restraints there.
6. If the surface is a generated artifact filename, asset-manifest path, committed media basename, or filename legend, MUST load modules/human-output-naming/SKILL.md (hon), call scripts/human_filename (speakable by default; optional safe_twin), and keep a per-feature legend.
7. Never treat HSW as optional, soft-skip, or per-report opt-in for human-facing HTML, compare UIs, or agent-produced readable artifacts.

## routes (Surface → module MUST load)

| Surfaces (sample) | MUST load |
| --- | --- |
| README.md; product entry pages | `writing-direction` |
| pull request titles; pull request bodies; issue titles; issue bodies; issue log titles; commit messages; commit subjects; non-README docs; ... | `human-sounding-writing` (hsw/HSW) |
| generated artifact filenames; asset-manifest paths; committed media basenames; filename legends | `human-output-naming` (hon/HON) |

Contract language is **MUST / APPLY / default_on**, not prefer. Soft enforcement = no NLP CI grade of prose.
