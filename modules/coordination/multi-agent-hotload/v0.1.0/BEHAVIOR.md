# BEHAVIOR — gold-standard multi-agent ops (normative)

Normative operating rules for agents hot-loading this ACS pack. This is **behavior and coordination**, not epistemic claim-graph data.

Owning issue: [#11](https://github.com/Pukujan/agent-custom-setup/issues/11).

## Triple wire (required)

When told to load the agent hot-loader into a working repo, wire **all three**:

1. **PCM** — checkout / continuity / checkpoints (not proposals)
2. **CGM** — HSW + writing-direction at pin `c7d9c3f6b5b301d3a3bc89642d2f92fd08748979` (0.5.0); re-pin **0.5.1** after CGM PR #17
3. **This runtime** — join-order roles, boss lease, agent-less watchdog, proposals → claim → PR

ACS installs them together; it does **not** replace or vendor PCM/CGM source.

## Role fill

- **Join/continue order** fills roles: first continuer = decision boss; next = coder1; next = coder2…
- Tool identity (Grok / Claude / Codex / …) does **not** assign roles
- Assignment list may seed; live fill wins

## Boss lease (hours)

- Authoritative seat is a **lease** (default **12h**, configurable **4–24h**)
- Agents emit check-in / heartbeat **stamps** only
- Keep **as-of history** (who was boss at T) separate from who-is-boss-now
- Do **not** use ~30m as failover

## Agent-less watchdog (~10m)

- Cron / GitHub Action / script only — **no LLM, no peer agent**
- Reads claim heartbeat + GitHub commit/PR stamps
- fresh → noop; stale idle → flag; past lease TTL → write `vacant` in claim file
- Watchdog ≠ failover; does not appoint a boss
- Stubs: `scripts/watchdog_check.py`, `workflow-stubs/watchdog.yml`

## Progress and delivery

- **GitHub is primary** progress truth (commits on claim branch, PR updates, dated progress comments)
- Local telemetry secondary only — never sole cross-machine truth
- Flow: propose → boss ACCEPT/REJECT → claim branch → PR
- Parent/child ticket **notes only** — no full DAG engine
- Human-readable issue / commit / PR titles (CGM HSW / writing-direction)
- PR-only to `main`; never force-push; never print secrets
- **ACS is SoT**; Desktop is deploy mirror only

## Citations (patterns — do not copy wholesale)

Read these in [Pukujan/jev-classifier](https://github.com/Pukujan/jev-classifier) for proven ops patterns. They are **references**, not files to vendor into ACS:

| Doc | Why cite |
| --- | --- |
| [`docs/AUTHORITY.md`](https://github.com/Pukujan/jev-classifier/blob/main/docs/AUTHORITY.md) | Who decides; project does not stop; GitHub canonical |
| [`docs/AGENT_PROPOSALS.md`](https://github.com/Pukujan/jev-classifier/blob/main/docs/AGENT_PROPOSALS.md) | Propose / verdict / claim / receipt mechanics |
| [`docs/HUMAN_NAMING.md`](https://github.com/Pukujan/jev-classifier/blob/main/docs/HUMAN_NAMING.md) | Human-readable titles; CGM HSW pins |

This pack's local projections of those ideas: [ROLES.md](ROLES.md), [PROPOSALS.md](PROPOSALS.md), [HOTLOAD.md](HOTLOAD.md).

## Explicit non-goals

- Not an epistemic claim-graph, JEV label store, or paper-claim schema
- Not a DAG engine or second product owner
- Not a watchdog LLM

## Canary / proof (join-order)

Proof of join-order fill requires **at least 2** shadow agents (prefer **3**) in a throwaway canary lane — never claim the real boss seat on production ACS work. Exercises: join-order roles, claim/heartbeat stamps, lease renewals vs HOTLOAD. Log observed vs expected; summarize on the owning issue.
