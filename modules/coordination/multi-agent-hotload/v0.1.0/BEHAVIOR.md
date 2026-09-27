# BEHAVIOR — gold-standard multi-agent ops (normative)

Normative operating rules for agents hot-loading this ACS pack. This is **behavior and coordination**, not epistemic claim-graph data.

Owning issue: [#11](https://github.com/Pukujan/agent-custom-setup/issues/11).

## Triple wire (required — full stacks)

When told to load the agent hot-loader into a working repo, wire **all three** as **complete** stacks (slim subsets fail closed):

1. **FULL PCM** @ `4e2385474b4af9249ca009cbdcb38c4498932475` (CLI **0.6.0**, protocol `0.1.0-draft`) — continuity/checkpoints **and** PR-only + required CI + branch-protection/auto-merge preference + fail-closed gates + receipts. Still not proposals/ACCEPT.
2. **FULL CGM 0.5.1** @ `9874b26dc46499137bf22e1ca163874ef2dd5e7a` — all seven modules + `human_output_contract` (not HSW + writing-direction only). README → writing-direction; posts/papers → hsw.
3. **This runtime** — join-order roles, boss lease (minutes), GitHub-canonical claim queue, agent-less watchdog, proposals → claim → PR

ACS installs them together; it does **not** replace or vendor PCM/CGM source. ACS and **all** hotloader adopters must use the full stacks.

`hotload_check` must run `scripts/validate_content_system.py` against the adopter `.content-system` and require stdout starting with `VALID`. After VALID, agents load modules per CGM `docs/WRITING_ROUTING.md` (prose quality remains agent discipline).

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

## Citations (patterns — do not copy wholesale)

Read these in [Pukujan/jev-classifier](https://github.com/Pukujan/jev-classifier) for proven ops patterns. They are **references**, not files to vendor into ACS:

| Doc | Why cite |
| --- | --- |
| [`docs/AUTHORITY.md`](https://github.com/Pukujan/jev-classifier/blob/main/docs/AUTHORITY.md) | Who decides; project does not stop; GitHub canonical |
| [`docs/AGENT_PROPOSALS.md`](https://github.com/Pukujan/jev-classifier/blob/main/docs/AGENT_PROPOSALS.md) | Propose / verdict / claim / receipt mechanics |
| [`docs/HUMAN_NAMING.md`](https://github.com/Pukujan/jev-classifier/blob/main/docs/HUMAN_NAMING.md) | Human-readable titles; align with FULL CGM 0.5.1 pins |

This pack's local projections of those ideas: [ROLES.md](ROLES.md), [PROPOSALS.md](PROPOSALS.md), [HOTLOAD.md](HOTLOAD.md).

## Explicit non-goals

- Not an epistemic claim-graph, JEV label store, or paper-claim schema
- Not a DAG engine or second product owner
- Not a watchdog LLM
- Not out-of-band DM for lease handoff
