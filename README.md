# Agent Custom Setup

![Catch mistakes earlier - Jev routing turns your constraints into checkpoints: a designer holding a constraint checklist at a warm evening desk while a small robot companion highlights one branch of a glowing route diagram](modules/coordination/jev-oss-compare/v0.1.0/reports/assets/jev-routing-hero.png)

> **One hotload pack that gives your coding agents decision gates, live loop defense, and offline benchmark receipts — installed into any repo without vendoring anything.**

## Why this exists

You give an agent a real brief: hosted API only, keys live at one path, don't touch that table. For the first hour it obeys. Then context compacts, a subagent paraphrases, or an advisory interrupts the flow, and the agent proposes a self-hosted build against a non-existent key path—confidently, mid-task, on work you thought was proceeding smoothly. You find out hours later: a failed deploy, a wrong turn, or an "impossible" you shouldn't have accepted.

The expensive part of agent work is no longer generating code. **It is drift you catch late.** Agent Custom Setup (ACS) answers that with one installable surface: the **multi-agent hotloader**. Point it at a working repo and it wires in a set of cheap decision gates placed at the moments drift first appears—your prompt, the agent's claims, the tool call it's about to make, the advice it's about to act on—plus the coordination rules that keep several agents on one repository honest. A gate doesn't stop the world when it sees something; it recommends a recovery route:

- `reconfirm_intent` — go back and re-check what the user actually asked;
- `rethink_plan` — the plan conflicts with a pinned instruction;
- `research_more` — the claim needs a source before action;
- `dispatch_verifier` — check this named claim against its source;
- `escalate` — a human should decide;
- `proceed` — covered, consistent, clear to go.

**A real failure built one of these gates.** In a voice-lab session, the brief said hosted API; after compaction the agent planned a self-hosted build, missed the free model, and reached for the wrong key path. That transcript became the Fish fixtures the hotloader installs: the tool gate must answer `deny` on the bad proposal, and the test suite requires zero missed blocks across the fixture set.

## What this project is

**The product you install is the multi-agent hotloader.** ACS is the registry and workshop that ships it: a versioned coordination pack that, dropped into any working repo, wires together the full Project Continuity Modules (PCM) delivery discipline, the full Content Generation Modules writing/visual contract, and this repository's Jev decision-gate runtime—without copying any of their source.

It is for operators who want **agents that flag their own drift while there's still time**, and for maintainers wiring several agents onto one repository. One command validates that an adopter repo has the whole stack pinned and loaded correctly.

The hotloader carries two supporting capability modules, which you can also run on their own:

- **`jev-omp`** — live runtime defense for the oh-my-pi harness: the `jev-court` advisor adjudicator and `loop-guard` that stop advisory storms and runaway loops in-session.
- **`jev-benchmark`** — the offline evaluation lab: compaction replay, a local CPU decision lane, transcript harvest datasets, and comparison reports that show what each decision lane actually did.

**What this project is not:**
- It is *not* a hosted platform — one decision lane calls a third-party model (TypeSafe Jev 1.13 on OpenRouter), priced and governed by that provider, while the primary local lane runs on CPU.
- It is *not* an accuracy guarantee — the local benchmark lane reports discovery-only numbers so far; the blind replay that would measure catch rate is open work ([issue #28](https://github.com/Pukujan/agent-custom-setup/issues/28)).
- It is *not* a secrets vault — keys, tokens, and `.env` values never enter this repository; only environment-variable names are referenced.

## What you can make or use

### The main feature: the multi-agent hotloader

[`modules/coordination/multi-agent-hotload/v0.1.0/`](modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md) is the user-facing entry point. An adopter repo loads `HOTLOAD.md` and gets a complete, pinned install:

- **Full-stack wiring** — PCM CLI 0.6.0 (@ `4e23854…`: PR-only delivery, required CI gates, protection/auto-merge preference, leaf/parent receipts) plus the full Content Generation Modules contract 0.5.7 (@ `c069613…`: all eight modules including human-output-naming), joined to the Jev gate runtime. A slim subset fails the install on purpose.
- **Coordination rules** — join-order roles, a boss **lease** with FIFO failover, a **claim queue**, and a **watchdog** that flags stale seats without making decisions ([`ROLES.md`](modules/coordination/multi-agent-hotload/v0.1.0/ROLES.md)).
- **Boot-time prompt injection** — [`PROMPT_INJECT.md`](modules/coordination/multi-agent-hotload/v0.1.0/PROMPT_INJECT.md) is generated from the pinned writing router and pasted into the agent system prompt at session start, so every fresh session inherits the same rules.
- **A one-command installer check** — [`hotload_check.py`](modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py) fails closed unless the assignment pins, the helper checkout revision, and the adapter validation all pass.

### What the hotloader carries: the supporting modules

![Three glowing cards above a dark desk - a judge gavel with a red loop arrow, a blue CPU chip with a yellow spark, and three agent figures reviewing a checklist - the hotloader's decision gates, live defense, and benchmark lane](assets/acs-three-modules.jpg)

Once installed, the hotloader brings the Jev decision gates and these two capability modules into the working repo:

- **`jev-omp` — live loop defense.** `jev-court.ts` scores incoming advisories against turn budgets and turns noisy background pings into structured `act` / `rethink` / `suppress` verdicts; `loop-guard.ts` breaks runaway cycles. On the real 94-note advisory-storm fixture ([issue #35](https://github.com/Pukujan/agent-custom-setup/issues/35)), v2 turned 83 unwanted injections into 0 while passing 38/38 assertions. Key paths: [`oh-my-pi/extensions/jev-court.ts`](oh-my-pi/extensions/jev-court.ts), [`oh-my-pi/extensions/loop-guard.ts`](oh-my-pi/extensions/loop-guard.ts), [`oh-my-pi/config/WATCHDOG.yml`](oh-my-pi/config/WATCHDOG.yml).
- **`jev-benchmark` — offline replay and receipts.** Replays real transcripts through compaction boundaries and scores typed recovery decisions on CPU, then writes pinned JSON receipts and comparison HTML. The capped local pilot completed 805/805 planned jobs over 7 of 80 streams. Key paths: [`modules/coordination/jev-oss-compare/v0.1.0/`](modules/coordination/jev-oss-compare/v0.1.0/README.md), [`laya_typed_decisions/v1/runner.py`](modules/coordination/jev-oss-compare/v0.1.0/scripts/laya_typed_decisions/v1/runner.py), [`reports/runs/laya-pilot-20260929.json`](modules/coordination/jev-oss-compare/v0.1.0/reports/runs/laya-pilot-20260929.json).

| Surface | What it is for | How you reach it | Status |
| --- | --- | --- | --- |
| **multi-agent-hotload** | Install the whole stack into a working repo | [`HOTLOAD.md`](modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md) + `hotload_check.py` | Shipped (PR #12) |
| **jev-omp** | Live advisory/loop defense in-session | [`oh-my-pi/extensions/`](oh-my-pi/extensions/) | Shipped (v2 court) |
| **jev-benchmark** | Offline decision scoring + receipts | [`modules/coordination/jev-oss-compare/`](modules/coordination/jev-oss-compare/v0.1.0/) | Active pilot (#28 open) |

## How it works

### Step 1: Install the hotloader into a repo

An adopter adds the pack, declares its pins in an assignment document, and runs `hotload_check.py`. The check resolves the pinned PCM and Content Generation Modules checkouts, runs the adapter validator, and only on success writes `PROMPT_INJECT.md` and prints the boot-time system block. Missing or stale pins fail closed — a partial install never looks complete.

### Step 2: The gates intercept agent actions

Inside the working repo, each gate packages a tiny constrained payload—the pinned constraints, recent tool outputs, and the proposed next action—and asks a cheap judge (local Laya CPU, a mock in CI, or the hosted lane) for a typed decision. A deterministic route policy then emits `reconfirm_intent` / `rethink_plan` / `research_more` / `dispatch_verifier` / `escalate` / `proceed`; incomplete or contradictory coverage can never silently proceed.

- **PreToolUse Gate (`jev-gate-pin`)**: checks tool calls against pinned brief boundaries — a self-host proposal under a hosted-only brief triggers `deny` + `rethink_plan`.
- **Prompt Ambiguity Gate (`jev-ambiguity-gate`)**: requests intent clarification on ambiguous prompts and resumptions.
- **Research Needed Gate (`jev-research-gate`)**: forces `research_more` on high-consequence claims made without a source.

### Step 3: Runtime defense keeps sessions from looping

Background advisories arrive constantly in multi-agent work. `jev-court.ts` checks the remaining advisory budget and turn counter; if an advisor tries to steer a settled decision, `loop-guard.ts` suppresses the interrupt so context can't run away. When real drift is detected, the court issues a typed verdict telling the agent to re-check the brief.

### Step 4: Offline replay proves the gates catch drift

To keep the gates honest without human babysitting, `jev-benchmark` replays recorded transcripts through the decision model: transcripts are stripped of secrets and ingested, the compaction lab recreates the exact moment of failure, and the Laya runner scores whether the gate would have caught the drift, writing typed receipts to `reports/runs/`.

## Evidence and boundaries

ACS grounds every public claim in versioned repository artifacts, committed evaluation receipts, or direct external records:

| Claim | Source | Status | What this supports | What this leaves unproven |
| --- | --- | --- | --- | --- |
| **The hotloader installs the full stack** | [`HOTLOAD.md`](modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md) | Shipped | Shipped via PR #12; pins PCM CLI 0.6.0 and Content Generation Modules 0.5.7; `hotload_check.py` fails closed on missing/stale pins. | Does not guarantee adopter agents honor every prompt rule; dependent gates remain opt-in. |
| **jev-court v2 stops advisory storms** | [`oh-my-pi/README.md`](oh-my-pi/README.md) | Shipped | Replay of the 94-note `#35` fixture passes 38/38 assertions; reduces 83 injections to 0. | Disabled by default; the async-result wake is harness-owned; live multi-day confirmation pending (#37). |
| **Local Laya CPU lane runs end-to-end** | [`laya-pilot-20260929.json`](modules/coordination/jev-oss-compare/v0.1.0/reports/runs/laya-pilot-20260929.json) | Experimentally supported | Completed 805/805 planned pilot jobs over 7 of 80 streams on local CPU. | Discovery-only on a truncated export; uncalibrated confidence (ECE 0.213); catch rate needs the 81-file blind replay ([#28](https://github.com/Pukujan/agent-custom-setup/issues/28)). |
| **Tool gate denies unpermitted self-hosting** | [`jev-gate-pin README`](modules/coordination/jev-gate-pin/v0.1.0/README.md) | Shipped | Fish fixtures require `deny` on the self-host proposal; zero false negatives required on the block set. | Registered as draft/optional; binding load-order across third-party harnesses is outside v0.1.0 scope. |
| **Hosted comparison decision endpoint exists** | [OpenRouter endpoint](https://openrouter.ai/api/v1/models/typesafe/jev-1.13/endpoints) | Shipped | Provider lists `typesafe/jev-1.13` text-to-decisions at $0.042/M prompt tokens, no completion fee. | Third-party pricing/availability can change; not exercised in CI; provider claims traceable, not verified by ACS. |
| **Three-module separation across codebase** | [Issue #44](https://github.com/Pukujan/agent-custom-setup/issues/44) | Planned | Proposal to decouple `jev-omp`, `jev-benchmark`, and the hotloader into distinct trees and CI. | Under active design; paths stay at current locations until the migration PR merges. |

### Operational Boundaries

- **No upstream replacement:** ACS does not replace Project Continuity Modules (PCM) or Content Generation Modules; it pins them as external authorities and never vendors their source.
- **Advisory safety net:** The gates and `jev-court` are advisory seatbelts. Final authority always belongs to the human operator.
- **Pilot vs. catch rate:** Benchmark pilot numbers are discovery-only sanity checks, not statistical guarantees of live detection.
- **Zero secrets in repository:** No API keys, credentials, session tokens, or `.env` files enter this repository. External model/provider keys are referenced only by environment-variable name.
- **Visual assets:** Two narrative rasters ship with the README (the brand hero and the three-module overview); full provenance — role, exact text, dimensions, prompt record, hash, review — lives in `.content-system/asset-manifest.json`. The compact blue SVG mark (`assets/registry-icon.svg`) remains the small registry seal.

## Try it

The fastest path is the installer check; the rest exercise what it brings in:

```bash
# 1. Validate a hotload install (schema-only here; a real install drops
#    --skip-cgm-validate and passes --cgm-root <checkout at c069613…>)
python3 modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py \
  --adopter-root . \
  --assignment modules/coordination/multi-agent-hotload/v0.1.0/examples/assignment.example.json \
  --skip-cgm-validate

# 2. Fish fixture gate: hosted-only brief denies the self-host proposal
#    (expect "decision": "deny" with reason_code fish_hosted_brief_selfhost_tool)
python3 modules/coordination/jev-gate-pin/v0.1.0/scripts/gate.py \
  --fixture modules/coordination/jev-gate-pin/v0.1.0/fixtures/fish_hosted_vs_selfhost/block_selfhost_despite_hosted_brief.json \
  --judge mock --json

# 3. Full gate test suite (requires pytest):
python3 -m pytest modules/coordination/jev-gate-pin/v0.1.0/tests/ -q

# 4. Verify oh-my-pi watchdog and court extension configurations (needs pyyaml)
python3 -c '
import yaml, json, glob
files = sorted(glob.glob("oh-my-pi/config/*.yml")) + sorted(glob.glob("oh-my-pi/config/*.json"))
for f in files:
    (json.load if f.endswith(".json") else yaml.safe_load)(open(f))
print(f"OK: {len(files)} config template(s) parsed successfully")
'
```
