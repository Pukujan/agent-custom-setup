# Multi-agent hotload coordination

**Install surface** for agents told to load the agent hot-loader into a working repo. This ACS module does **not** replace PCM or CGM. It hot-loads **all three** together:

1. **PCM** — checkout / continuity / checkpoints
2. **CGM** — human-sounding writing (HSW) + writing-direction
3. **This runtime** — join-order roles, boss lease (**minutes**, default 30), GitHub-canonical claim queue, agent-less watchdog (~10m), proposals, claim → PR

Pin and reference PCM/CGM only — **do not copy** their source into ACS.

**Version:** 0.1.0  
**Harness:** `coordination`  
**Path:** `modules/coordination/multi-agent-hotload/v0.1.0/`  
**Owning issue:** [#11](https://github.com/Pukujan/agent-custom-setup/issues/11)

ACS is the source of truth for this pack. Desktop paths are deploy mirrors only — sync **from ACS → mirrors** after an accepted merge.

## Done when (install criteria)

An agent that was told to load this hot-loader into a working repo has finished only when **all** of the following are true:

- [ ] **PCM** is available and used for checkout/continuity/checkpoints (not for proposals).
- [ ] **CGM** is pinned and used for titles/UX: HSW + writing-direction at pin `c7d9c3f6b5b301d3a3bc89642d2f92fd08748979` (HSW 0.5.0). After CGM PR #17 merges, re-pin to **0.5.1**. Paths: `modules/human-sounding-writing`, `modules/writing-direction`.
- [ ] **This runtime** is loaded: [HOTLOAD.md](HOTLOAD.md), [ROLES.md](ROLES.md), [BEHAVIOR.md](BEHAVIOR.md), [PROPOSALS.md](PROPOSALS.md), and a valid assignment with **boss_failover** (minutes + `claim_queue`) + **watchdog** (agent-less).
- [ ] `hotload_check` passes.

Missing any of the three is an incomplete install.

## Role fill order (binding)

Tool identity (Grok / Claude / Codex / …) **does not** assign roles. **Live join/continue order** does:

1. First agent that opens the hot-loaded working repo and continues = **decision boss**
2. Next continuing agent = **coder1**
3. Next = **coder2**, …

Assignment list may **seed** order; live join/continue order **fills** roles. See [ROLES.md](ROLES.md).

## Boss lease vs agent-less watchdog

| | Boss lease / failover | Watchdog |
| --- | --- | --- |
| Cadence | **Minutes** (default **30**; range **15–120**) | ~**10 minutes** |
| Runner | Agents emit check-in stamps; after vacancy, FIFO `claim_queue` on GitHub | **Cron / GitHub Action / script only** — no LLM, no peer agent |
| Effect | Vacant seat after TTL; **front of queue** takes boss; old boss rejoins at **end** | Liveness flags; may write `vacant` in claim file after lease TTL |
| Must not | Auto-reclaim for returning boss; skip zombie re-read | Make product decisions or appoint a new boss agent |

**Watchdog ≠ failover.** Schema separates `lease_ttl_minutes`, `claim_queue`, `watchdog_interval_minutes`, and `idle_window`.

**Zombie:** on wake, re-read GitHub claim. If vacant/not you → reject boss actions; worker or re-queue; optional issue comment `lost lease → rejoining queue`; no out-of-band DM.

Progress signals: **GitHub primary** (commits on claim branch, PR updates, dated progress comments, claim/`claim_queue`). Optional local telemetry secondary only.

Logic: fresh heartbeat → noop; stale + recent git/PR → nudge, keep boss; stale + idle past window → at risk; past lease TTL → write vacant; agents enqueue afterward.

Details: [HOTLOAD.md](HOTLOAD.md). Skeleton: `scripts/watchdog_check.py`, `workflow-stubs/watchdog.yml`.

## Install / hotload

1. Ensure ACS is checked out and current (`git fetch`, re-read `POLICY.md` + `registry.json`).
2. Point the agent (or session brief) at this module path.
3. On start, follow **[HOTLOAD.md](HOTLOAD.md)** (PCM → CGM → this pack).
4. Confirm join order / lease / queue / watchdog config via assignment example or project live assignment.
5. Run:

```bash
python modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py
```

## Binding owner rules (summary)

1. **Join/continue order fills roles** (first = decision boss; next = coder1…). Seed list optional; live fill wins.
2. Decision boss **may also do tasks**; deciding wins on conflict.
3. Boss seat is a **lease in minutes** (default 30; 15–120) with check-in stamps; missed check-in past TTL vacates the seat.
4. After vacancy: **GitHub-canonical FIFO `claim_queue`**; front takes boss; returning boss joins at **end**.
5. **Zombie:** re-read GitHub claim on wake; reject boss actions if not named; worker or re-queue; optional issue comment; no DM.
6. **Watchdog is agent-less** (cron/Action/script, ~10m); agents only emit stamps.
7. Reuse **PCM** and **CGM** as pins — never vendor their trees here.
8. Human-readable titles (CGM HSW / writing-direction).
9. Ticket parent/child notes only — no DAG engine.
10. Never commit secrets; never force-push; never commit straight to `main`.

## Layout

| Path | Role |
| --- | --- |
| `HOTLOAD.md` | Startup load order + lease vs agent-less watchdog + queue |
| `ROLES.md` | Join-order fill, boss vs workers, failover, zombie |
| `BEHAVIOR.md` | Normative ops summary |
| `PROPOSALS.md` | Propose → ACCEPT/REJECT → claim → PR |
| `README.md` | This file |
| `NOTES.md` | Operator notes |
| `module.json` | ACS multi-setup metadata |
| `schema/assignment.schema.json` | Assignment + boss_failover + claim_queue + watchdog |
| `examples/assignment.example.json` | Example with lease/queue/watchdog/standby |
| `scripts/hotload_check.py` | Validate pack + assignment |
| `scripts/watchdog_check.py` | Agent-less watchdog skeleton |
| `workflow-stubs/watchdog.yml` | GH Action stub (copy into consuming repos) |
| `tests/test_hotload_check.py` | Regression tests |

## Reference pins (do not vendor)

| Pin | Role |
| --- | --- |
| PCM | Continuity only — not proposals |
| CGM @ `c7d9c3f…` (0.5.0); re-pin 0.5.1 after PR #17 | HSW + writing-direction |
| Project pattern docs (e.g. Jev proposals/authority/naming) | Read via GitHub; do not copy wholesale |

## Related ACS docs

- [`POLICY.md`](../../../../POLICY.md) · [`registry.json`](../../../../registry.json) · [`AGENTS.md`](../../../../AGENTS.md)
