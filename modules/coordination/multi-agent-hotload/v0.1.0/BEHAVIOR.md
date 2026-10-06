# BEHAVIOR — gold-standard multi-agent ops (normative)

Normative operating rules for agents hot-loading this ACS pack. This is **behavior and coordination**, not epistemic claim-graph data.

Owning issue: [#11](https://github.com/Pukujan/agent-custom-setup/issues/11).

## Quad wire (required — full stacks)

When told to load the agent hot-loader into a working repo, wire **all four** as **complete** stacks (slim subsets fail closed). Versions come from the release train through `stack-mesh.json`; the adopter's `stack-manifest.json` follows the train with empty pins ([SPEC.md](SPEC.md) §1) — do not copy commits into this file.

1. **FULL PCM** — continuity/checkpoints **and** PR-only + required CI + branch-protection/auto-merge preference + fail-closed gates + receipts. Still not proposals/ACCEPT. See [adopter-enforcement](https://github.com/Pukujan/project-continuity-modules/blob/main/docs/adopter-enforcement.md).
2. **FULL CGM 0.5.12** — all eight modules + `human_output_contract` (not HSW + writing-direction only). README → writing-direction; posts/papers → hsw.
3. **OIO** — the observational issue-log surface (ontology, issue form, triage workflow, `AGENTS.md` guidance block). A component that cannot be installed is reported **PARTIAL**, never OK.
4. **This runtime** — join-order roles, boss lease (minutes), GitHub-canonical claim queue, agent-less watchdog, proposals → claim → PR

ACS installs them together; it does **not** replace or vendor PCM/CGM/OIO source. ACS and **all** hotloader adopters must use the full stacks.

`hotload_check` must run `scripts/validate_content_system.py` against the adopter `.content-system` and require stdout starting with `VALID`. After VALID, agents **MUST load** modules per CGM `docs/writing-routing.json` / `docs/ACS_VERIFY.md` (README→writing-direction; PR/issue/docs/commits/HTML reports/compare/appendable→hsw (default ON); basenames→hon) and paste `acs_prompt_inject.system_block` into system prompt at **boot** (see `PROMPT_INJECT.md`; always_on, not per-report). Soft = no NLP CI; language is MUST/APPLY.

## Role fill

- **Join/continue order** fills roles: first continuer = decision boss; next = coder1; next = coder2…
- Tool identity (Grok / Claude / Codex / …) does **not** assign roles
- Assignment list may seed; live fill wins

## Boss lease (minutes) + claim queue

- Authoritative seat is a **lease** (default **30 minutes**, configurable **15–120 minutes**)
- Agents emit check-in / heartbeat **stamps** only
- After vacancy: claimants form a **FIFO `claim_queue`** on the **GitHub-canonical** claim; **front** takes next boss
- **Returning / old boss** joins from the **end of the queue** — **no automatic reclaim**
- Keep **as-of history** (who was boss at T) separate from who-is-boss-now
- **Zombie rule:** on every wake, re-read GitHub claim. If vacant or not you → reject boss-only actions; drop to worker or re-queue at end; optional issue comment `lost lease → rejoining queue`; **no out-of-band DM**

## Agent-less watchdog (~10m)

- Cron / GitHub Action / script only — **no LLM, no peer agent**
- Reads claim heartbeat + GitHub commit/PR stamps
- fresh → noop; stale idle → flag; past lease TTL → write `vacant` in claim file
- Watchdog ≠ failover; does not appoint a boss; does not reorder `claim_queue`
- Stubs: `scripts/watchdog_check.py`, `workflow-stubs/watchdog.yml`

## Progress and delivery

- **GitHub is primary** progress truth (commits on claim branch, PR updates, dated progress comments, claim / `claim_queue`)
- Local telemetry secondary only — never sole cross-machine truth
- Flow: propose → boss ACCEPT/REJECT → claim branch → PR
- Parent/child ticket **notes only** — no full DAG engine
- Human-readable issue / commit / PR titles under FULL CGM (README → writing-direction; other prose → hsw)
- PR-only to `main`; never force-push; never print secrets
- **ACS is SoT**; Desktop is deploy mirror only

## Working-repo scope (binding)

Adopters using ACS / this multi-agent hotloader may only write code on **their own working repo** — the GitHub repo they hot-loaded into / own as the adopter project.

| Rule | Binding |
| --- | --- |
| **MUST** | Commits, branches, PRs, claims, and boss actions (ACCEPT/REJECT, lease renew as boss, queue mutations) only on the hot-loaded working repo |
| **MUST NOT** | Push code, open PRs, claim branches, ACCEPT/REJECT, or otherwise mutate **other projects' repositories** |
| **Exception (narrow)** | MAY report findings to another repo's **issue log only** as a **proposed ticket** (open or comment a Proposal-style issue/ticket). Issue-log only — no code, no claim, no PR, no boss actions on the foreign repo |

Cross-repo help stays at the ticket/proposal layer until that foreign project's own agents accept and implement on **their** working repo.

## Dev root hygiene (binding)

The dev root (`ACS_DEV_ROOT`; default `D:\development` on Windows, `~/development` elsewhere) holds one entry per repo. Same strength as Working-repo scope.

| Rule | Binding |
| --- | --- |
| **MUST** | Give each repo one project folder: the primary checkout at `<project>/main`, task worktrees at `<project>/worktrees/<task>`, nothing else in the folder |
| **MAY** | Keep a legacy flat checkout (`<dev root>/<repo>`) for a repo without worktrees; migrate it (`dev_root_check.py --migrate <repo>`) before adding any |
| **MUST NOT** | Put a worktree directly in the dev root or inside a main checkout |
| **MUST NOT** | Put dependency or sibling clones, pinned copies, scratch folders, or caches in the dev root |
| **MUST** | Put those under the ACS cache: `%LOCALAPPDATA%\acs\{deps,scratch}` on Windows, `~/.cache/acs/{deps,scratch}` on macOS/Linux (`ACS_CACHE_DIR` overrides) |
| **MUST** | Before ending a session, remove the worktrees and scratch you created, after pushing any real work to a branch |
| **MUST NOT** | Delete or move a checkout that has uncommitted, unpushed, or stashed work in order to tidy up |

`scripts/dev_root_check.py` reports every entry that does not fit this layout and prints JSON; `--clean` plans a fix and `--migrate <repo>` plans the move from a flat checkout to a project folder, and both only act with `--yes`. `hotload_check` runs the check and warns (or fails with `--strict-dev-root`).

## External research gate (binding)

Selective + version-pinned official docs — **not** always-on research. Same strength as Working-repo scope.

| Rule | Binding |
| --- | --- |
| **MUST research** when | (1) First use / introduce of external OSS, SDK, CLI, API, framework, or cloud service; (2) Version bump of such a dependency; (3) Install / runtime / API failure involving that external surface |
| **MUST** when triggered | Exact version in use; official primary docs + changelog/migration notes **for that version**; on failure also skim public issue tracker / release notes for matching version/error; paste the checklist below onto the GitHub issue/PR |
| **MUST NOT** | Require research for every trivial in-repo edit of already-known patterns |

### Provenance checklist (paste into issue/PR when gate triggers)

```markdown
### External research provenance
- Artifact / surface:
- Exact version (source: lockfile | package metadata | image tag | git tag | CLI --version):
- Official docs URL (this version):
- Changelog / migration notes URL (this version):
- Issue tracker / release notes skimmed? (required on failure): yes/no — URL(s):
- Learned (2–5 lines):
```

## Coordination patterns

This pack defines its own coordination rules; they are not vendored from any other project:

| Doc | What it defines |
| --- | --- |
| [ROLES.md](ROLES.md) | Join-order role fill, boss lease, claim queue, watchdog-as-liveness-only |
| [PROPOSALS.md](PROPOSALS.md) | Propose / ACCEPT-REJECT / claim / PR mechanics |
| [HOTLOAD.md](HOTLOAD.md) | Load order, full-stack pins, verify, dev root hygiene |

## Explicit non-goals

- Not an epistemic claim-graph, label store, or paper-claim schema
- Not a decision-making or adjudication layer
- Not a DAG engine or second product owner
- Not a watchdog LLM
- Not out-of-band DM for lease handoff
