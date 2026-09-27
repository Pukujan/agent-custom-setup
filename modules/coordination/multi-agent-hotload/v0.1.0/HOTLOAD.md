# HOTLOAD — what to load first on ACS

When an agent starts on Agent Custom Setup (or is told to load the **agent hot-loader** into a working repo), load in this order. This module is the **install surface**: it wires PCM + CGM + this coordination runtime together. ACS does **not** replace PCM or CGM.

## Done when

Install is complete only when all three are wired:

1. PCM available for checkout / continuity / checkpoints
2. CGM pinned for HSW + writing-direction
3. This runtime loaded (join-order roles, boss **lease** failover, **watchdog** liveness, proposals, claim → PR)

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

### 4. This runtime (roles + lease + watchdog + proposals + claim)

1. [ROLES.md](ROLES.md) — **live join/continue order** fills roles (first = decision boss, next = coder1…). Tool identity does not matter. Assignment may seed; live fill wins.
2. Assignment document — start from `examples/assignment.example.json`. Must include required **`boss_failover`** (lease TTL in **hours**) and **`watchdog`** (interval in **minutes**). **Watchdog ≠ failover.**
3. Establish or renew the boss **lease check-in** (issue comment or claim file per assignment).
4. [PROPOSALS.md](PROPOSALS.md) — propose → boss ACCEPT/REJECT → claim branch → PR.
5. Know your current role from join order + whether the boss lease is still valid.

### 5. Boss lease vs watchdog (read carefully)

| Concept | Cadence | What it does | What it must NOT do |
| --- | --- | --- | --- |
| **Boss lease / failover** | Hours — default **12h**, configurable **4–24h** (`lease_ttl_hours`) | Vacates the authoritative seat after missed check-in past TTL; next continuer (or standby) may claim boss | Must **not** use ~30m (or other short windows) as failover |
| **No-agent watchdog** | About every **10m** (`watchdog_interval_minutes`) | Liveness / stale-seat **flagging** only | Must **not** make product decisions or auto-reassign boss |

Do **not** treat the watchdog interval as the boss failover TTL.

#### Progress signals

- **Primary (cross-machine truth):** GitHub — commits on the claim branch, PR updates, dated progress comments on the owning issue.
- **Secondary only:** optional local telemetry (PCM checkpoint mtime, last git activity in the checkout). Never sole cross-machine truth.

#### Combined logic

1. **Fresh heartbeat** (check-in within idle/watch expectations) → noop.
2. **Stale heartbeat + recent git/PR activity** → nudge check-in; **keep boss**.
3. **Stale heartbeat + no activity past `idle_window`** → seat **at risk** (flag only).
4. **After `lease_ttl_hours` with no valid check-in** → seat **vacant**; next continuing agent (or named standby) may claim boss. Optional takeover proposal + short grace if configured.

### 6. Boss lease check (every session)

Before acting as decision boss:

1. Read `boss_failover.lease_ttl_hours` (default 12; range 4–24 — **hours**, not minutes).
2. Find the latest check-in for the authoritative seat (`check_in.mechanism`: `issue_comment` or `claim_file`).
3. If last check-in is within TTL → current boss remains; renew check-in when you continue.
4. If past TTL → seat vacant. Next continuing agent, or named `standby`, may claim boss and post a new check-in. Append as-of history (who was boss at T); do not rewrite who-is-boss-now into old history.
5. Optional path: worker posts a takeover proposal; if old boss is past lease and does not refute within `grace_minutes`, accept.

### 7. Verify

```bash
python modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py
```

`hotload_check` requires `boss_failover` and `watchdog` fields on the assignment document, and checks that lease TTL stays in the 4–24 hour band (not a short watchdog-sized window).

## Minimal session checklist

- [ ] PCM ready (continuity only)
- [ ] CGM pinned (HSW + writing-direction)
- [ ] Join order understood; I know boss / coderN for this session
- [ ] Boss lease checked or renewed (or seat claimed after vacancy) — lease is **hours**
- [ ] Watchdog understood as **liveness only** (~10m), not failover
- [ ] Titles will be human-readable
- [ ] I will not treat PCM as the proposal layer
- [ ] Parent/child ticket notes only (no DAG engine)
- [ ] No secrets in commits, logs, or comments

## Gold-standard behavior

Normative ops rules (not epistemic claim-graph): [BEHAVIOR.md](BEHAVIOR.md). Cites Jev AUTHORITY / AGENT_PROPOSALS / HUMAN_NAMING as references only.

## Canary / proof (join-order)

Proof of join-order fill requires **at least 2** shadow agents (prefer **3**) in a throwaway canary lane — never claim the real boss seat on production ACS work. Exercises: join-order roles, claim/heartbeat stamps, lease renewals vs HOTLOAD. Log observed vs expected; summarize on the owning issue.
