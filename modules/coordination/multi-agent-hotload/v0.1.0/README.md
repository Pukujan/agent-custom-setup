# Multi-agent hotload coordination

**Install surface** for agents told to load the agent hot-loader into a working repo. This ACS module does **not** replace PCM or CGM. It hot-loads **all three** together:

1. **FULL PCM** (`4e2385474b4af9249ca009cbdcb38c4498932475`, CLI **0.6.0**) — continuity/checkpoints **plus** PR-only workflow, required CI gates, branch-protection + auto-merge preference, fail-closed gates, issue receipts
2. **FULL CGM 0.5.12** (`6831f91e165b62d719c05eb492f7375fa932b560`) — all eight modules + `human_output_contract` (not HSW + writing-direction only)
3. **This runtime** — join-order roles, boss lease (**minutes**, default 30), GitHub-canonical claim queue, agent-less watchdog (~10m), proposals, claim → PR

Pin and reference PCM/CGM only — **do not copy** their source into ACS. A slim subset is an **incomplete install** for ACS and every hotloader adopter.

**Version:** 0.1.0  
**Harness:** `coordination`  
**Path:** `modules/coordination/multi-agent-hotload/v0.1.0/`  
**Owning issue:** [#11](https://github.com/Pukujan/agent-custom-setup/issues/11)

ACS is the source of truth for this pack. Desktop paths are deploy mirrors only — sync **from ACS → mirrors** after an accepted merge.

## Done when (install criteria)

An agent that was told to load this hot-loader into a working repo has finished only when **all** of the following are true:

- [ ] **FULL PCM** pinned and used: continuity/checkpoints **and** GitHub governance (PR-only, required CI, protection/auto-merge preference, fail-closed) per [`docs/adopter-enforcement.md`](https://github.com/Pukujan/project-continuity-modules/blob/main/docs/adopter-enforcement.md). Still not the proposal layer.
- [ ] **FULL CGM 0.5.12** pinned at `6831f91e…` with **all eight** module ids + human_output_contract docs. Route README via writing-direction; human-facing prose/HTML/compare/appendable via hsw (default ON); basenames via hon. Not a two-module subset.
- [ ] **This runtime** is loaded: [HOTLOAD.md](HOTLOAD.md), [ROLES.md](ROLES.md), [BEHAVIOR.md](BEHAVIOR.md), [PROPOSALS.md](PROPOSALS.md), and a valid assignment with **boss_failover** (minutes + `claim_queue`) + **watchdog** (agent-less) + full `pins.pcm` / `pins.cgm`.
- [ ] `hotload_check` passes (enforces full pin module lists on the assignment example).

Missing any of the three, or using a slim PCM/CGM subset, is an incomplete install.

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
5. Point `CGM_ROOT` at content-generation-modules checked out at `6831f91e165b62d719c05eb492f7375fa932b560` (0.5.12). Ensure the adopter has `.content-system/` listing all eight modules.
6. Run:

```bash
python modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py \
  --cgm-root "$CGM_ROOT" --adopter-root "$ADOPTER_ROOT"
```

`hotload_check` runs `validate_content_system.py` and **fails** unless stdout starts with `VALID`. No HSW-only shortcut.
7. **After VALID:** MUST load modules per [`docs/writing-routing.json`](https://github.com/Pukujan/content-generation-modules/blob/6831f91e165b62d719c05eb492f7375fa932b560/docs/writing-routing.json) / [`ACS_VERIFY.md`](https://github.com/Pukujan/content-generation-modules/blob/6831f91e165b62d719c05eb492f7375fa932b560/docs/ACS_VERIFY.md) (README/product → writing-direction; PR/issue/docs/commits/HTML reports/compare/appendable → hsw (default ON); basenames → hon). Paste `acs_prompt_inject.system_block` (see [`PROMPT_INJECT.md`](PROMPT_INJECT.md)) into the agent system prompt at **boot** (always_on; not per-report). Before Pages/compare publish: `verify_hsw_applied.py --mode acs-html --html <compare.html>`. Soft = no NLP CI; language is MUST/APPLY.

## Binding owner rules (summary)

1. **Join/continue order fills roles** (first = decision boss; next = coder1…). Seed list optional; live fill wins.
2. Decision boss **may also do tasks**; deciding wins on conflict.
3. Boss seat is a **lease in minutes** (default 30; 15–120) with check-in stamps; missed check-in past TTL vacates the seat.
4. After vacancy: **GitHub-canonical FIFO `claim_queue`**; front takes boss; returning boss joins at **end**.
5. **Zombie:** re-read GitHub claim on wake; reject boss actions if not named; worker or re-queue; optional issue comment; no DM.
6. **Watchdog is agent-less** (cron/Action/script, ~10m); agents only emit stamps.
7. Reuse **FULL PCM** and **FULL CGM 0.5.12** as pins — never vendor their trees; never ship a slim subset.
8. Human-readable titles under the CGM stack (README → writing-direction; other prose → hsw).
9. Ticket parent/child notes only — no DAG engine.
10. Never commit secrets; never force-push; never commit straight to `main`.
11. **Working-repo scope (binding):** code, claims, PRs, and boss actions only on the hot-loaded working repo; foreign repos = proposed issue/ticket only (no code/claim/PR/boss there).
12. **External research gate:** see [BEHAVIOR.md](BEHAVIOR.md) (selective MUST/MUST NOT + provenance checklist; not always-on).

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
| `scripts/dev_root_check.py` | Flag (and optionally clean up) anything in the dev root that is not a single main checkout |
| `workflow-stubs/watchdog.yml` | GH Action stub (copy into consuming repos) |
| `tests/test_hotload_check.py` | Regression tests |
| `tests/test_dev_root_check.py` | Dev root check tests (fake dev roots under `tmp_path`) |

## Reference pins (do not vendor)

| Pin | Role |
| --- | --- |
| PCM @ `4e23854…` (CLI 0.6.0) | **Full** continuity + PR-only + required CI + protection/auto-merge preference — not proposals ; [adopter-enforcement](https://github.com/Pukujan/project-continuity-modules/blob/main/docs/adopter-enforcement.md) |
| CGM @ `6831f91e…` (**0.5.12**) | **Full** eight modules + human_output_contract — not HSW+WD only |

## Related ACS docs

- [`POLICY.md`](../../../../POLICY.md) · [`registry.json`](../../../../registry.json) · [`AGENTS.md`](../../../../AGENTS.md)

## Adopter root README (product-only)

Hotload may pin CGM for install. The **working-repo root README** stays product story only (audience, problem, features, evidence). No CGM methodology theater; no image-generation README section (provenance in `.content-system/asset-manifest.json`). CGM 0.5.12 / #25; see [README_PLAYBOOK.md](https://github.com/Pukujan/content-generation-modules/blob/6831f91e165b62d719c05eb492f7375fa932b560/docs/README_PLAYBOOK.md).
