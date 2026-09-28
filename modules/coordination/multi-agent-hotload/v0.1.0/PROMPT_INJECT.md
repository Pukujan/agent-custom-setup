# PROMPT_INJECT — acs_prompt_inject (CGM 0.5.6)

Generated / refreshed by `hotload_check` after full adapter `VALID`.
Source: CGM `docs/writing-routing.json` → `acs_prompt_inject` @ `32de5cf9341b36673a05a4a17b1868b2178362f8`.

Also see: CGM [`docs/ACS_VERIFY.md`](https://github.com/Pukujan/content-generation-modules/blob/32de5cf9341b36673a05a4a17b1868b2178362f8/docs/ACS_VERIFY.md) and [`docs/writing-routing.json`](https://github.com/Pukujan/content-generation-modules/blob/32de5cf9341b36673a05a4a17b1868b2178362f8/docs/writing-routing.json).

**Pin:** CGM `0.5.6` @ `32de5cf9341b36673a05a4a17b1868b2178362f8` (main). After any future CGM merge that moves the tip, re-pin ACS hotload to the new main SHA.

## application

`must_load` — agents MUST load the listed module before writing each surface.

## When

After hotload_check / CGM_VERIFY succeeds, before the agent writes ANY human-facing deliverable: GitHub or docs prose, HTML reports, compare HTML/UIs, appendable HTML, posts, papers, or other agent-produced human-readable artifacts — and before naming generated artifact / asset-manifest / media paths.

## human_facing_default

- **load:** `human-sounding-writing` (**hsw**) — `required_load: true`, `default_on: true`
- **covers:** `every human-facing task/output`, `HTML reports`, `compare HTML`, `compare UIs`, `agent-produced human-readable HTML`, `agent-produced human-readable artifacts with prose`, `GitHub and docs prose`, `posts blogs social`, `papers and data writeups`
- **exceptions:** `readme_product_entry`, `generated_artifact_filenames` (README/product → writing-direction; basenames → **hon**)
- **rule:** HSW is ON by default for EVERY human-facing task/output including HTML reports, compare HTML/UIs, and appendable HTML. Not optional. Not per-report opt-in. Visible HTML prose → **hsw**; filesystem basenames → **hon**.

## Instruction (MUST paste/apply into system or task prompts)

Inject into the agent system or task prompt: HSW (human-sounding-writing) is ON by default for EVERY human-facing task/output. For every route with required_load true, you MUST load modules/<load>/SKILL.md before writing any listed surface. README and product entry pages → writing-direction. Pull request titles/bodies, issue titles/bodies, issue-log titles, commit messages, commit subjects, non-README docs, changelog prose, posts/blogs/social/general prose, papers/data writeups, HTML reports, compare HTML, compare UIs, appendable HTML reports, and other agent-produced human-readable HTML → human-sounding-writing (hsw). Do NOT treat HSW as optional, per-report, or only-when-writing-posts. Soft enforcement means no NLP CI grade of prose; the contract language is MUST/APPLY/default_on, not prefer. Follow apply_checklist and human_facing_default in this file. Generated artifact filenames, asset-manifest paths, committed media basenames, and filename legends → human-output-naming (hon): MUST load that skill and use scripts/human_filename with speakable basenames (omit defaults; optional safe_twin); keep a per-feature legend (glossary + file list); never opaque p0/hex stems or robot key=value stems. Prose and visible text inside HTML still use hsw; basenames use hon.

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
