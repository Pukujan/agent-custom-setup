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
- Holds the authoritative seat only under a valid **lease** (hours — see below).
- Uses human-readable titles (CGM HSW / writing-direction).

## Workers (coder1, coder2, …)

- **Propose only** until the boss accepts.
- Do not self-arbitrate or overrule other workers.
- After ACCEPT: claim the reserved branch, implement within scope, open a small issue-linked PR.
- On collision (branch exists / claim held): stop, comment on the issue, take other work.
- Never force-push; never commit to `main`.
- May become boss only via **lease failover** when the seat is vacant (or via accepted takeover) — **not** via the ~10m watchdog.

## Boss may also work

The boss can be a coding agent. Being boss does not forbid shipping code; it forbids skipping the decision step when a proposal is contested.

## Boss failover (required) — lease in hours

The authoritative seat is a **lease**, not a forever label. Failover TTL is measured in **hours** (default **12**; configurable **4–24**). Do **not** use ~30 minutes (or the watchdog interval) as boss failover.

| Field | Meaning |
| --- | --- |
| `lease_ttl_hours` | How long a check-in stays valid. **Default 12.** Projects set **4–24**. |
| `check_in.mechanism` | `issue_comment` (preferred shared) or `claim_file` (repo-local path named in assignment). |
| `check_in.interval_hint_hours` | How often the sitting boss should renew (typically ≤ TTL; still in hours). |
| `standby` | Optional ordered `agent_id` list preferred when the seat goes vacant. If none continue, any next joiner may claim. |
| `grace_minutes` | Short window for old boss to refute a takeover proposal **after lease TTL expiry** (optional path). Not the failover TTL itself. |
| `as_of_history` | Append-only notes of who was boss at time T. **Separate** from who-is-boss-now. Never rewrite history to match the current seat. |

### Vacancy and claim

1. Sitting boss renews check-in while active.
2. Missed check-in past **lease TTL (hours)** → seat **vacant**.
3. Named standby (if continuing) or the next continuing agent may claim boss: post a new check-in and append as-of history.
4. Optional: a worker proposes takeover; if old boss is past lease and does not refute within grace, accept and record as-of.

Who-is-boss-now is the agent with the latest valid check-in inside TTL. As-of history answers "who was boss at T?" without mutating current seat state.

## Watchdog ≠ failover

Automated **no-agent watchdog** (~every **10 minutes**, `watchdog_interval_minutes`) only does **liveness / stale-seat flagging**. It does **not** make product decisions and does **not** reassign the boss seat.

| Signal | Role |
| --- | --- |
| Fresh heartbeat | noop |
| Stale heartbeat + recent GitHub git/PR activity | nudge check-in; **keep boss** |
| Stale heartbeat + no activity past `idle_window` | seat **at risk** (flag) |
| Past `lease_ttl_hours` with no valid check-in | seat **vacant** → next continuer claims boss |

**Progress signals:** GitHub is primary (commits on claim branch, PR updates, dated progress comments). Optional local telemetry (PCM checkpoint mtime, last git activity in checkout) is secondary only — never sole cross-machine truth.

Schema fields `lease_ttl_hours`, `watchdog_interval_minutes`, and `idle_window` are distinct on purpose. See [HOTLOAD.md](HOTLOAD.md).

## What is not a role authority

| System | Role |
| --- | --- |
| PCM | Continuity / checkpoints — **not** boss, not proposal store, not lease store of record (GitHub issue comments preferred for check-ins) |
| CGM | Writing quality for titles/UX — **not** ownership |
| Tool brand (Grok/Claude/Codex/…) | Irrelevant to seat assignment |
| Watchdog | Liveness flags only — not failover |
| Local SQLite / device DBs | Execution aids — GitHub issues win on disagreement |
| ACS this pack | Install surface that hot-loads PCM + CGM + these role rules |

## Example fill (illustrative)

| Join order | Agent id (example) | Role filled |
| --- | --- | --- |
| 1st to continue | `claude-code-main` | Decision boss (lease starts) |
| 2nd | `jev-classifier@teresa` | coder1 |
| 3rd | `omp@macbookpro` | coder2 |

If boss lease expires (hours) and `omp@macbookpro` continues first, omp may claim boss; prior boss becomes a worker on next join unless they reclaim under failover rules. A 10-minute stale watchdog flag alone does **not** hand the seat over.

See `examples/assignment.example.json` for `boss_failover` and `watchdog` shape.
