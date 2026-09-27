# PROMPT_INJECT — acs_prompt_inject (CGM 0.5.4)

Generated / refreshed by `hotload_check` after full adapter `VALID`.
Source: CGM `docs/writing-routing.json` → `acs_prompt_inject` @ `c95d73a0ce072a6d7173ce4848621a25cdf1cc7e`.

Also see: CGM [`docs/ACS_VERIFY.md`](https://github.com/Pukujan/content-generation-modules/blob/c95d73a0ce072a6d7173ce4848621a25cdf1cc7e/docs/ACS_VERIFY.md) and [`docs/writing-routing.json`](https://github.com/Pukujan/content-generation-modules/blob/c95d73a0ce072a6d7173ce4848621a25cdf1cc7e/docs/writing-routing.json).

## When

After `hotload_check` / full adapter validate succeeds, **before** writing PR/issue/docs/commits (or any routed surface).

## Instruction (MUST paste/apply into system or task prompts)

Inject into the agent system or task prompt: For every route with required_load true, you MUST load modules/<load>/SKILL.md before writing any listed surface. README and product entry pages → writing-direction. Pull request titles/bodies, issue titles/bodies, issue-log titles, commit messages, commit subjects, non-README docs, changelog prose, posts/blogs/social/general prose, and papers/data writeups → human-sounding-writing (hsw). Soft enforcement means no NLP CI grade of prose; the contract language is MUST/APPLY, not prefer. Follow apply_checklist in this file.

## apply_checklist

1. Identify the writing surface (README, PR title/body, issue title/body, issue-log title, commit message/subject, non-README doc, changelog prose, post/blog/social, paper/data writeup).
2. Look up the surface in routes[].surfaces in docs/writing-routing.json (or the table in docs/WRITING_ROUTING.md).
3. MUST load modules/<load>/SKILL.md for that route before drafting — required_load is true; do not skip because the surface is short or 'just a commit'.
4. Apply the module rules to the draft (voice, AI-tell scrub, bold policy as the module states).
5. README / product entry stays on writing-direction; do not apply hsw bold restraints there.

## Surface → module (MUST load)

| Surface | MUST load |
| --- | --- |
| README / product entry | `writing-direction` |
| PR titles/bodies, issue titles/bodies, issue-log titles, commit messages/subjects, non-README docs, changelog prose, posts/blogs/social/general prose, papers/data writeups | `human-sounding-writing` (**hsw**) |

Contract language is **MUST / APPLY**, not prefer. Soft enforcement = no NLP CI grade of prose.
