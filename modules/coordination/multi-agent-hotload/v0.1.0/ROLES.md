# ROLES — join order, decision boss, workers, failover

Binding owner rules for multi-agent work coordinated through this ACS pack.

## Role fill order (binding)

**Tool identity does not assign roles.** Grok, Claude, Codex, or any other harness may hold any seat. What matters is **who opens the hot-loaded working repo and continues**:

1. First agent that joins/continues = **decision boss**
2. Next continuing agent = **coder1**
3. Next = **coder2**, then **coder3**, …

An assignment document may **seed** a preferred agent list. Seeding is a hint for humans and for empty rooms. When agents actually join, **live join/continue order fills (and re-fills) roles**. If seed list and live order disagree while filling vacant seats, **live join/continue order wins**.

## Decision boss

- Sole arbiter of proposals: comments ACCEPT or REJECT (see [PROPOSALS.md](PROPOSALS.md)).
- **May also implement tasks** on accepted work.
- If "decide" and "do" conflict in the same moment, **deciding wins** — rule first, then optionally execute.
- Holds the authoritative seat only under a valid **lease** (minutes — see below) **and** while GitHub-canonical `who_is_boss_now` / claim file names them.
- Uses human-readable titles (FULL CGM (README→writing-direction; prose→hsw)).

## Workers (coder1, coder2, …)

- **Propose only** until the boss accepts.
- Do not self-arbitrate or overrule other workers.
- After ACCEPT: claim the reserved branch, implement within scope, open a small issue-linked PR.
- On collision (branch exists / claim held): stop, comment on the issue, take other work.
- Never force-push; never commit to `main`.
- May become boss only via **lease failover** when the seat is vacant and they reach the **front of `claim_queue`** (or via accepted takeover that respects the queue) — **not** via the ~10m watchdog.

## Boss may also work

The boss can be a coding agent. Being boss does not forbid shipping code; it forbids skipping the decision step when a proposal is contested.

## Boss failover (required) — lease in minutes + claim queue

The authoritative seat is a **lease**, not a forever label. Failover TTL is measured in **minutes** (default **30**; configurable **15–120**). The agent-less watchdog stays ~**10 minutes** for liveness/nudge only — it does **not** appoint a boss.

| Field | Meaning |
| --- | --- |
| `lease_ttl_minutes` | How long a check-in stays valid. **Default 30.** Projects set **15–120**. |
| `check_in.mechanism` | `issue_comment` (preferred shared) or `claim_file` (repo-local path named in assignment). |
| `check_in.interval_hint_minutes` | How often the sitting boss should renew (typically ≤ TTL). |
| `claim_queue` | **GitHub-canonical FIFO** of `agent_id`s waiting after vacancy. **Front takes next boss.** |
| `standby` | Optional preferred `agent_id` hints when enqueueing. Live `claim_queue` order wins. |
| `grace_minutes` | Short window for old boss to refute a takeover proposal **after lease TTL expiry** (optional path). Not the failover TTL itself. |
| `as_of_history` | Append-only notes of who was boss at time T. **Separate** from who-is-boss-now. Never rewrite history to match the current seat. |
| `who_is_boss_now` | Current holder or `null` if vacant. **Authoritative with the claim file.** |

### Vacancy, queue, and claim

1. Sitting boss renews check-in while active.
2. Missed check-in past **lease TTL (minutes)** → seat **vacant** (watchdog may write `vacant`; it does not appoint).
3. Claimants form a **queue** on the GitHub-canonical claim (`claim_queue`). Next continuer takes boss from the **front**.
4. **Returning / old boss:** if they come alive again, they join from the **end of the queue** — **no automatic reclaim** of boss.
5. Optional: a worker proposes takeover; if old boss is past lease and does not refute within grace, accept and record as-of — still must not silently skip FIFO without an accepted queue-reorder proposal.
6. Append as-of history on seat change; never rewrite past entries.

Who-is-boss-now is the agent named on the live claim inside TTL. As-of history answers "who was boss at T?" without mutating current seat state.

### Zombie boss (binding)

On every wake, **re-read the GitHub claim** (`who_is_boss_now` / claim file + `claim_queue`).

If you still believe you are boss but the claim says **vacant** or **names someone else**:

1. **Reject boss-only actions** (proposal ACCEPT/REJECT, renewing as boss, appointing others).
2. Drop to **worker** **or** **re-queue** at the end of `claim_queue`.
3. Optionally comment on the owning issue: `lost lease → rejoining queue`.
4. **No out-of-band DM** for handoff or reclaim.
5. Keep **as-of history** intact (append only).

## Watchdog ≠ failover

Automated **no-agent watchdog** (~every **10 minutes**, `watchdog_interval_minutes`) only does **liveness / stale-seat flagging**. It does **not** make product decisions and does **not** reassign the boss seat.

| Signal | Role |
| --- | --- |
| Fresh heartbeat | noop |
| Stale heartbeat + recent GitHub git/PR activity | nudge check-in; **keep boss** |
| Stale heartbeat + no activity past `idle_window` | seat **at risk** (flag) |
| Past `lease_ttl_minutes` with no valid check-in | seat **vacant** → claimants enqueue; front of queue takes boss |

**Progress signals:** GitHub is primary (commits on claim branch, PR updates, dated progress comments, claim/`claim_queue`). Optional local telemetry is secondary only — never sole cross-machine truth.

Schema fields `lease_ttl_minutes`, `claim_queue`, `watchdog_interval_minutes`, and `idle_window` are distinct on purpose. See [HOTLOAD.md](HOTLOAD.md).

## What is not a role authority

| System | Role |
| --- | --- |
| PCM | **Full** continuity + PR-only/gates/protection/auto-merge preference — **not** boss, not proposal store, not lease store of record |
| CGM | **Full** 0.5.1 stack (seven modules + contracts) for titles/README/UX — **not** ownership |
| Tool brand (Grok/Claude/Codex/…) | Irrelevant to seat assignment |
| Watchdog | Liveness flags only — not failover |
| Local SQLite / device DBs | Execution aids — GitHub issues / claim win on disagreement |
| Out-of-band DM | **Forbidden** for lease handoff |
| ACS this pack | Install surface that hot-loads FULL PCM + FULL CGM 0.5.1 + these role rules |

## Example fill (illustrative)

| Join order | Agent id (example) | Role filled |
| --- | --- | --- |
| 1st to continue | `claude-code-main` | Decision boss (lease starts) |
| 2nd | `jev-classifier@teresa` | coder1 |
| 3rd | `omp@macbookpro` | coder2 |

If boss lease expires (**minutes**) and the seat is vacant, `jev-classifier@teresa` and `omp@macbookpro` enqueue; the **front** of `claim_queue` takes boss. If `claude-code-main` wakes later as a zombie, they **re-read GitHub claim**, reject boss actions, and join the **end** of the queue (or work as a worker). A 10-minute stale watchdog flag alone does **not** hand the seat over.

See `examples/assignment.example.json` for `boss_failover` and `watchdog` shape.
