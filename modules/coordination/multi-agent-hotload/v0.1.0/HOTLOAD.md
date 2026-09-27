# HOTLOAD — what to load first on ACS

When an agent starts on Agent Custom Setup (or is told to load the **agent hot-loader** into a working repo), load in this order. This module is the **install surface**: it wires PCM + CGM + this coordination runtime together. ACS does **not** replace PCM or CGM.

## Done when

Install is complete only when all three are wired:

1. PCM available for checkout / continuity / checkpoints
2. CGM pinned for HSW + writing-direction
3. This runtime loaded (join-order roles, boss **lease** failover, **claim queue**, **watchdog** liveness, proposals, claim → PR)

## Load order

### 1. ACS policy and registry (always)

1. `POLICY.md` — ACS is SoT; PR-only to `main`; no secrets; path layout.
2. `registry.json` — confirm this module is registered (`multi-agent-hotload` @ `0.1.0`).
3. This pack's `module.json` and `NOTES.md`.

### 2. PCM (continuity only)

- Checkout / worktree / continuity / checkpoints.
- **Not** for proposals, ACCEPT/REJECT, or work locks — those live in [PROPOSALS.md](PROPOSALS.md) and GitHub issues.
- Pin or check out `project-continuity-modules` per the working repo's PCM instructions; do not copy PCM source into ACS.

### 3. CGM (human titles and UX)

Pin [Pukujan/content-generation-modules](https://github.com/Pukujan/content-generation-modules) at:

- **Current:** `c7d9c3f6b5b301d3a3bc89642d2f92fd08748979` (HSW **0.5.0**)
- **After CGM PR #17 merges:** re-pin to **0.5.1**

Load:

| Module | Path in CGM |
| --- | --- |
| Human-sounding writing (HSW) | `modules/human-sounding-writing` (see also `SKILL.md`) |
| Writing direction | `modules/writing-direction` |

Use these for issue titles, commit subjects, PR titles, and human-facing UX prose. Do not copy CGM source into ACS.

### 4. This runtime (roles + lease + queue + watchdog + proposals + claim)

1. [ROLES.md](ROLES.md) — **live join/continue order** fills roles (first = decision boss, next = coder1…). Tool identity does not matter. Assignment may seed; live fill wins.
2. Assignment document — start from `examples/assignment.example.json`. Must include required **`boss_failover`** (lease TTL in **minutes**, default **30**, range **15–120**) and **`watchdog`** (~**10m** agent-less). **Watchdog ≠ failover.**
3. Establish or renew the boss **lease check-in** (issue comment or claim file per assignment). On every wake, **re-read the GitHub-canonical claim** (`who_is_boss_now` / claim file + `claim_queue`).
4. [PROPOSALS.md](PROPOSALS.md) — propose → boss ACCEPT/REJECT → claim branch → PR.
5. Know your current role from join order + whether the boss lease is still valid for **you**.

### 5. Boss lease vs watchdog (read carefully)

| Concept | Cadence | What it does | What it must NOT do |
| --- | --- | --- | --- |
| **Boss lease / failover** | Minutes — default **30m**, configurable **15–120m** (`lease_ttl_minutes`) | Vacates the authoritative seat after missed check-in past TTL; claimants form a **FIFO queue**; front takes boss | Must **not** auto-reclaim for a returning old boss; must **not** treat watchdog as failover |
| **No-agent watchdog** | About every **10m** (`watchdog_interval_minutes`) | Liveness / stale-seat **flagging** only; may write `vacant` after lease TTL | Must **not** make product decisions or appoint a boss |

Do **not** treat the watchdog interval as the boss failover TTL. Short leases (tens of minutes) are intentional; watchdog stays ~10m for nudge/flag only.

#### Progress signals

- **Primary (cross-machine truth):** GitHub — commits on the claim branch, PR updates, dated progress comments on the owning issue, and the **GitHub-canonical claim / `claim_queue`**.
- **Secondary only:** optional local telemetry (PCM checkpoint mtime, last git activity in the checkout). Never sole cross-machine truth. **No out-of-band DM** for lease handoff.

#### Combined logic

1. **Fresh heartbeat** (check-in within idle/watch expectations) → noop.
2. **Stale heartbeat + recent git/PR activity** → nudge check-in; **keep boss**.
3. **Stale heartbeat + no activity past `idle_window`** → seat **at risk** (flag only).
4. **After `lease_ttl_minutes` with no valid check-in** → seat **vacant**; claimants **enqueue** on the GitHub-canonical `claim_queue`; **front of queue** takes boss next.

### 6. Boss lease check (every session) + zombie rule

Before acting as decision boss:

1. Read `boss_failover.lease_ttl_minutes` (default **30**; range **15–120**).
2. **Re-read GitHub claim** (`who_is_boss_now` / claim file + `claim_queue`). That record is authoritative.
3. If last check-in is within TTL **and** `who_is_boss_now` is you → you remain boss; renew check-in when you continue.
4. If past TTL → seat vacant. Claimants join the **queue**; next continuer takes boss from the **front**. Append as-of history (who was boss at T); do not rewrite who-is-boss-now into old history.
5. **Returning / old boss:** if the previous boss comes alive again, they join from the **end of the queue** — **no automatic reclaim**.
6. **Zombie boss:** if you still think you are boss but the claim says vacant or names someone else → **reject boss-only actions** (ACCEPT/REJECT, lease renew as boss). Drop to worker **or** re-queue at the end. Optionally comment on the owning issue: `lost lease → rejoining queue`. Do **not** DM out-of-band.
7. Optional path: worker posts a takeover proposal; if old boss is past lease and does not refute within `grace_minutes`, accept and record as-of — still enqueue-aware; no skip-ahead of the FIFO queue without explicit boss ACCEPT of a queue reorder proposal.

### 7. Verify

```bash
python modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py
```

`hotload_check` requires `boss_failover` and `watchdog` fields on the assignment document, checks that lease TTL stays in the **15–120 minute** band (default 30), and that `claim_queue` (when present) is a FIFO list of agent ids.

## Minimal session checklist

- [ ] PCM ready (continuity only)
- [ ] CGM pinned (HSW + writing-direction)
- [ ] Join order understood; I know boss / coderN for this session
- [ ] Re-read GitHub claim / `who_is_boss_now` / `claim_queue` on wake
- [ ] Boss lease checked or renewed (or enqueued after vacancy) — lease is **minutes** (default 30)
- [ ] If zombie: reject boss actions; worker or re-queue; optional issue comment; no DM
- [ ] Watchdog understood as **liveness only** (~10m), not failover
- [ ] Titles will be human-readable
- [ ] I will not treat PCM as the proposal layer
- [ ] Parent/child ticket notes only (no DAG engine)
- [ ] No secrets in commits, logs, or comments
