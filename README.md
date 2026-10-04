# Agent Custom Setup

![One pack. Any repo. - The multi-agent hotloader installs decision gates into your coding agents: a developer slides a glowing install pack into a laptop showing a repository tree while three small agent figures light up checkpoint nodes on a route diagram](assets/acs-readme-hero.png)

> **One hotload pack that gives several coding agents a shared way to work one repository — roles, a decision boss, lease failover, and proposals that become PRs — installed into any repo without vendoring anything.**

## Why this exists

Put three agents on one repository and the hard problem is not the code. It is
**who decides, who is working, and who is allowed to act.** Two agents claim the
same task. A seat goes quiet and nobody notices for an hour. An agent drafts a
change nobody approved, or a returning agent acts on a lease it no longer holds.
The work is fine; the coordination is not.

Agent Custom Setup (ACS) answers that with one installable surface: the
**multi-agent hotloader**. Point it at a working repo and it wires in the rules
that keep several agents honest on one repository — **join-order roles**, a
**decision boss**, a **lease** that fails over when a seat goes stale, a FIFO
**claim queue**, and **proposals** that only become PRs after the boss accepts
them. It installs those rules on top of the full continuity and writing
contracts, so a fresh session inherits the same discipline as the last one.

## What this project is

**The product you install is the multi-agent hotloader.** ACS is the registry and
workshop that ships it: a versioned coordination pack that, dropped into any
working repo, wires together the full Project Continuity Modules (PCM) delivery
discipline, the full Content Generation Modules writing/visual contract, and
this repository's coordination runtime — without copying any of their source.

It is for operators running **several agents on one repository** who need a
shared, explicit answer to *who is boss, who is working, and how does work get
approved*, and for maintainers who want that discipline installed with one
command that fails closed on a partial install.

**What this project is not:**
- It is *not* a decision-making or benchmarking layer — that work is parked
  outside this repository, and ACS makes no decisions on an agent's behalf.
- It is *not* a hosted platform — it is a set of rules, documents, and a
  validator you run yourself.
- It is *not* a secrets vault — keys, tokens, and `.env` values never enter this
  repository; only environment-variable names are referenced.

## What you can make or use

### The main feature: the multi-agent hotloader

[`modules/coordination/multi-agent-hotload/v0.1.0/`](modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md)
is the user-facing entry point. An adopter repo loads `HOTLOAD.md` and gets a
complete, pinned install:

- **Full-stack wiring** — PCM CLI 0.6.0 (@ `4e23854…`: PR-only delivery, required
  CI gates, protection/auto-merge preference, leaf/parent receipts) plus the full
  Content Generation Modules contract 0.5.12 (@ `6831f91e…`: all eight modules
  including human-output-naming), joined to the coordination runtime. A slim
  subset fails the install on purpose.
- **Coordination rules** — join-order roles, a boss **lease** with FIFO failover,
  a **claim queue**, and a **watchdog** that flags stale seats without making
  decisions ([`ROLES.md`](modules/coordination/multi-agent-hotload/v0.1.0/ROLES.md)).
- **Proposals to PRs** — propose → boss ACCEPT/REJECT → claim a branch → PR
  ([`PROPOSALS.md`](modules/coordination/multi-agent-hotload/v0.1.0/PROPOSALS.md)).
- **Boot-time prompt injection** —
  [`PROMPT_INJECT.md`](modules/coordination/multi-agent-hotload/v0.1.0/PROMPT_INJECT.md)
  is generated from the pinned writing router and pasted into the agent system
  prompt at session start, so every fresh session inherits the same rules.
- **A one-command installer check** —
  [`hotload_check.py`](modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py)
  fails closed unless the assignment pins, the helper checkout revision, and the
  adapter validation all pass.

| Surface | What it is for | How you reach it | Status |
| --- | --- | --- | --- |
| **multi-agent-hotload** | Install the coordination stack into a working repo | [`HOTLOAD.md`](modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md) + `hotload_check.py` | Shipped (PR #12) |
| **registry.json** | Declare which modules ACS ships | [`registry.json`](registry.json) | Shipped |
| **POLICY.md** | Authority, PR-only rule, path layout | [`POLICY.md`](POLICY.md) | Shipped |

## How it works

### Step 1: Install the hotloader into a repo

An adopter adds the pack, declares its pins in an assignment document, and runs
`hotload_check.py`. The check resolves the pinned PCM and Content Generation
Modules checkouts, runs the adapter validator, and only on success writes
`PROMPT_INJECT.md` and prints the boot-time system block. Missing or stale pins
fail closed — a partial install never looks complete.

### Step 2: Roles fill by join order

Whoever continues first becomes the **decision boss**; the next is `coder1`, then
`coder2`. A seed list in the assignment is a hint only — live join order wins, and
tool identity is irrelevant
([`ROLES.md`](modules/coordination/multi-agent-hotload/v0.1.0/ROLES.md)).

### Step 3: The boss holds a lease, and it fails over

The decision boss checks in on a **lease** measured in minutes (default **30**,
range **15–120**). Miss check-ins past the TTL and the seat goes vacant;
claimants form a **FIFO claim queue** and the front takes boss. A returning old
boss rejoins at the **end** of the queue — no automatic reclaim. A zombie boss
that still thinks it holds the seat must reject boss-only actions and re-queue.
A separate **watchdog** runs every ~10 minutes, agent-less, and only *flags* a
stale seat — it never appoints a boss or makes decisions. **Watchdog ≠ failover.**

### Step 4: Work becomes a PR through a proposal

An agent proposes; the boss ACCEPTs or REJECTs; an accepted proposal claims a
branch and lands as a PR. Nothing goes straight to the protected default branch,
and required CI gates must pass on the exact candidate before merge.

## Evidence and boundaries

ACS grounds every public claim in versioned repository artifacts:

| Claim | Source | Status | What this supports | What this leaves unproven |
| --- | --- | --- | --- | --- |
| **The hotloader installs the full stack** | [`HOTLOAD.md`](modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md) | Shipped | Shipped via PR #12; pins PCM CLI 0.6.0 and Content Generation Modules 0.5.12; `hotload_check.py` fails closed on missing/stale pins. | Does not guarantee adopter agents honor every rule; enforcement depends on the adopter's own CI and branch protection. |
| **Pin drift is caught, not assumed** | [`pins.json`](modules/coordination/multi-agent-hotload/v0.1.0/pins.json) + [`check_pins.py`](modules/coordination/multi-agent-hotload/v0.1.0/scripts/check_pins.py) | Shipped | The checker scans every declared projection for the pinned PCM/CGM commits, version families, and the "eight modules" count; CI runs it on every candidate. | It verifies that declared projections agree; it cannot see a surface nobody declared. |
| **Roles, lease, and queue are specified** | [`ROLES.md`](modules/coordination/multi-agent-hotload/v0.1.0/ROLES.md) | Shipped | Join-order fill, boss lease (default 30m, range 15–120m), FIFO claim queue, watchdog-as-liveness-only, and the zombie rule are written down as binding. | A specification is not an enforcement mechanism; adherence is a process commitment. |
| **Proposals gate the path to PR** | [`PROPOSALS.md`](modules/coordination/multi-agent-hotload/v0.1.0/PROPOSALS.md) | Shipped | Propose → boss ACCEPT/REJECT → claim → PR; no direct commits to the protected default branch. | Relies on the adopter enabling branch protection and required checks. |

### Operational Boundaries

- **No upstream replacement:** ACS does not replace Project Continuity Modules
  (PCM) or Content Generation Modules; it pins them as external authorities and
  never vendors their source.
- **Coordination, not decision-making:** the boss ACCEPT/REJECT gate is a
  governance rule, not an automated judge; final authority always belongs to the
  human operator.
- **No decisions on the agent's behalf:** ACS ships no model, no judge, and no
  benchmark; decision-making is out of scope here.
- **Zero secrets in repository:** No API keys, credentials, session tokens, or
  `.env` files enter this repository. Any external keys are referenced only by
  environment-variable name.
- **Visual assets:** One narrative raster ships with the README — the hotloader
  install hero ("One pack. Any repo.") — rendered with the current image model;
  full provenance (role, exact text, dimensions, prompt record, hash, review)
  lives in `.content-system/asset-manifest.json`. The compact blue SVG mark
  (`assets/registry-icon.svg`) remains the small registry seal.

## Try it

The fastest path is the installer check; the rest exercise what it brings in:

```bash
# 1. Validate a hotload install (schema-only here; a real install drops
#    --skip-cgm-validate and passes --cgm-root <checkout at 6831f91e…>)
python3 modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py \
  --adopter-root . \
  --assignment modules/coordination/multi-agent-hotload/v0.1.0/examples/assignment.example.json \
  --skip-cgm-validate

# 2. Fail-closed pin drift check across every declared projection
python3 modules/coordination/multi-agent-hotload/v0.1.0/scripts/check_pins.py

# 3. Coordination pack test suite (requires pytest)
python3 -m pytest modules/coordination/multi-agent-hotload/v0.1.0/tests -q
```
