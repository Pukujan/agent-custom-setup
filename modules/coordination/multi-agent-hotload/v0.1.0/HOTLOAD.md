# HOTLOAD — what to load first on ACS

When an agent starts on Agent Custom Setup (or is told to load the **agent hot-loader** into a working repo), load in this order. This module is the **install surface**: it wires PCM + CGM + this coordination runtime together. ACS does **not** replace PCM or CGM.

## Done when

Install is complete only when all three are wired as **full stacks** (slim subsets fail):

1. **FULL PCM** — continuity/checkpoints **and** GitHub-owned progression: PR-only to default branch, required CI gates, adopter branch-protection + auto-merge preference, fail-closed on missing/failed/skipped gates, leaf/parent receipts (see SPEC §8 / TARGET_ADOPTION). Still **not** the proposal/ACCEPT layer.
2. **FULL CGM 0.5.1** — all seven modules + `human_output_contract` docs (not HSW + writing-direction only). Route README/product entry via `writing-direction`; posts/papers via `human-sounding-writing` (hsw).
3. **This runtime** — join-order roles, boss **lease** failover, **claim queue**, **watchdog** liveness, proposals, claim → PR

Missing any of the three, or substituting a thin PCM/CGM subset, is an **incomplete install**.

## Load order

### 1. ACS policy and registry (always)

1. `POLICY.md` — ACS is SoT; PR-only to `main`; no secrets; path layout.
2. `registry.json` — confirm this module is registered (`multi-agent-hotload` @ `0.1.0`).
3. This pack's `module.json` and `NOTES.md`.

### 2. FULL PCM (continuity + GitHub governance)

Pin [Pukujan/project-continuity-modules](https://github.com/Pukujan/project-continuity-modules) at:

- **Commit:** `4e2385474b4af9249ca009cbdcb38c4498932475`
- **CLI:** `0.6.0` · **Protocol:** `0.1.0-draft`
- Do **not** silently follow moving `main`. Do **not** copy PCM source into ACS.

Wire the **complete** adopter surface (see PCM `docs/TARGET_ADOPTION.md`, `SPEC.md` §8, `AGENTS.md`):

| Required | Meaning |
| --- | --- |
| Continuity files + CLI | checkout / worktree / checkpoints / `continuity` validate+preflight when the target uses PCM |
| Issues own progression | GitHub issues own scope, acceptance, owner, deps, lifecycle; docs are projections |
| PR-only | never commit straight to the protected default branch; branch → PR → squash merge when required |
| Required CI gates | protected required checks on the exact candidate; missing/failed/skipped/stale = fail-closed |
| Branch protection | adopters should enable protection on default branch (ACS tracks its own gates in [#5](https://github.com/Pukujan/agent-custom-setup/issues/5)) |
| Auto-merge preference | enable GitHub auto-merge so green required checks can merge without skipping gates |
| Receipts | leaf issue receipt keyed by push SHA + parent progression link after pushes |

**Still not PCM's job:** proposals, ACCEPT/REJECT, or work locks — those live in [PROPOSALS.md](PROPOSALS.md) and GitHub issues.

### 3. FULL CGM 0.5.1 (all modules + contracts)

Pin [Pukujan/content-generation-modules](https://github.com/Pukujan/content-generation-modules) at:

- **Version:** `0.5.1`
- **Commit:** `9874b26dc46499137bf22e1ca163874ef2dd5e7a`
- Do **not** silently follow moving `main`. Do **not** copy CGM source into ACS.
- Adapter shape: target `.content-system/system-version.json` lists all seven module ids; validate with `python scripts/validate_content_system.py --root <cgm> --adapter <target>/.content-system --project-root <target>`.

**Required modules** (complete stack — a two-module pin is incomplete):

| Module id | Path | Load when |
| --- | --- | --- |
| `brand-foundation` | `modules/brand-foundation` | audience, promise, boundaries, brand-language |
| `content-context` | `modules/content-context` | evidence-bounded project brief / claim records |
| `writing-direction` | `modules/writing-direction` | README / product entry (scan-first selective bold) |
| `human-sounding-writing` | `modules/human-sounding-writing` | posts, blogs, papers, general prose (short name **hsw** / HSW) |
| `visual-direction` | `modules/visual-direction` | visual system / rejection conditions |
| `image-generation` | `modules/image-generation` | narrative assets + asset-manifest records |
| `html-demo` | `modules/html-demo` | responsive HTML demos when requested |

**human_output_contract** (always available at the pin; apply for README/product entry):

- `docs/README_PLAYBOOK.md`, `templates/README.template.md`, `templates/readme-contract.json`, `schemas/readme-contract.schema.json`
- `docs/README_QUALITY_{PDD,SDD,TDD}.md`, `docs/PROVENANCE_AND_CITATION.md`
- `docs/WRITING_ROUTING.md`, `docs/HUMAN_SOUNDING_WRITING.md`, `docs/human-sounding-rules.json`
- `docs/IMAGE_GUIDE.md`, `docs/CONTENT_RESEARCH.md`, `docs/BRAND_DIRECTION.md`
- scanability + claim-evidence contracts in `system-version.json` / readme-contract
- `AGENTS.md`

**Routing (binding):** README/product entry → `writing-direction` (keep scan/bold). Posts/papers/general prose → `human-sounding-writing`. Do **not** apply HSW bold restraints to READMEs. Titles for issues/commits/PRs stay human-readable under this stack.

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

- [ ] FULL PCM pinned (`4e23854…` / CLI 0.6.0) — continuity **and** PR-only + required gates + protection/auto-merge preference
- [ ] FULL CGM 0.5.1 pinned (`9874b26…`) — all seven modules + human_output_contract (not HSW+WD only)
- [ ] Join order understood; I know boss / coderN for this session
- [ ] Re-read GitHub claim / `who_is_boss_now` / `claim_queue` on wake
- [ ] Boss lease checked or renewed (or enqueued after vacancy) — lease is **minutes** (default 30)
- [ ] If zombie: reject boss actions; worker or re-queue; optional issue comment; no DM
- [ ] Watchdog understood as **liveness only** (~10m), not failover
- [ ] Titles will be human-readable
- [ ] I will not treat PCM as the proposal layer
- [ ] Parent/child ticket notes only (no DAG engine)
- [ ] No secrets in commits, logs, or comments
