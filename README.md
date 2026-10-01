# Agent Custom Setup

![Compact blue registry seal: the ACS mark for versioned agent setups](assets/registry-icon.svg)

> **Jev routing and multi-agent coordination: three dedicated modules that help coding agents catch their own mistakes early, benchmark recovery decisions, and hotload shared team protocol.**

## Why this exists

You give an agent a real brief: hosted API only, keys live at one path, don't modify database schemas without approval. For the first hour it obeys. Then context compacts, a subagent paraphrases, or an advisory interrupts the flow, and the agent proposes a self-hosted build against a non-existent key path—confidently, mid-task, on work you thought was proceeding smoothly. You find out hours later through a failed deployment, broken environment, or unnecessary rewrite.

The expensive part of agent work is no longer generating code. **It is drift you discover too late.** Jev routing is this repository's architectural answer: small, cheap decision gates placed at the exact moments drift first appears—user prompt intake, agent factual claims, tool execution proposals, and advisory recommendations. A gate does not blindly halt execution; it recommends an explicit recovery route:

- `reconfirm_intent` — return to the prompt and verify what the user actually requested;
- `rethink_plan` — the proposed step directly conflicts with a pinned constraint;
- `research_more` — the claim requires verifiable source evidence before execution;
- `dispatch_verifier` — check this named claim against its primary source;
- `escalate` — ambiguous or destructive situation requiring human judgment;
- `proceed` — covered, consistent, and clear to execute.

**A real failure built one of these gates.** In a voice-lab session, the operator's brief specified a hosted API only; after context compaction, the agent planned a self-hosted engine build, missed the free model tier, and reached for an invalid key path. That transcript became the Fish fixtures in [`modules/coordination/jev-gate-pin/v0.1.0/`](modules/coordination/jev-gate-pin/v0.1.0/README.md): the pre-tool gate must return `deny` on the self-host proposal, and test suites require zero false negatives across the fixture set.

To keep these capabilities maintainable, ACS organizes its work into three distinct operational modules: **`jev-omp`** for live runtime defense in oh-my-pi, **`jev-benchmark`** for offline evaluation on developer transcripts, and **`multi-agent-hotload`** for installing multi-agent protocols into target repositories.

## What this project is

**agent-custom-setup** (ACS) is the registry and workshop for Jev routing decision gates, live agent runtime extensions, transcript evaluation benchmarks, and multi-agent coordination protocols.

It is for operators who need **agents that catch their own drift before shipping**, maintainers coordinating multiple agents across one repository, and researchers benchmarking cheap decision lanes against real developer transcripts.

It is organized into three distinct, first-class modules:

1. **Jev oh-my-pi Integration (`jev-omp`)**: Live runtime defense extensions for the oh-my-pi agent harness, featuring the `jev-court` advisor adjudicator, `loop-guard` loop breaker, and watchdog configuration.
2. **Jev Benchmark Lab (`jev-benchmark`)**: Offline replay and evaluation laboratory, housing the compaction lab, local blind replay, Laya typed decision CPU runners, walkforward harvest datasets, and HTML comparison reports.
3. **Multi-Agent Hotloader (`multi-agent-hotload`)**: Turnkey coordination pack that wires full Project Continuity Modules (PCM CLI 0.6.0) and Content Generation Modules (0.5.7 pin) into working repositories without vendoring their source.

**What this project is not:**
- It is *not* a hosted platform — one lane calls a third-party decisions model (TypeSafe Jev 1.13 on OpenRouter), priced and governed by that provider, while the primary local lane runs on CPU.
- It is *not* an ungrounded accuracy guarantee — the local benchmark lane reports discovery-only metrics so far; measuring full blind catch rates is open work ([issue #28](https://github.com/Pukujan/agent-custom-setup/issues/28)).
- It is *not* a secrets vault: keys, tokens, and `.env` values never enter this repository; only environment-variable names are referenced.

## What you can make or use

ACS provides three distinct modules you can run, evaluate, or install into other repositories:

### 1. Jev oh-my-pi Module (`jev-omp`)

The live runtime extension module for the oh-my-pi agent harness. It prevents advisory storms and runaway agent loops while enforcing decision policies:

- **Advisory Adjudication (`jev-court.ts`)**: Evaluates incoming background advisories against turn budgets, turning noisy background notifications into structured `act`, `rethink`, or `suppress` verdicts.
- **Loop Hardening (`loop-guard.ts`)**: Intercepts repetitive agent cycles and runaway turns. Replay of the real 94-note advisory storm fixture ([issue #35](https://github.com/Pukujan/agent-custom-setup/issues/35)) proved that `jev-court` v2 reduced 83 unwanted injections down to 0 while satisfying 38/38 assertions.
- **Watchdog Control (`WATCHDOG.yml`)**: Pinned configuration templates governing turn limits, tool timeouts, and advisory budgets.
- **Key paths:** [`oh-my-pi/extensions/jev-court.ts`](oh-my-pi/extensions/jev-court.ts), [`oh-my-pi/extensions/loop-guard.ts`](oh-my-pi/extensions/loop-guard.ts), [`oh-my-pi/config/WATCHDOG.yml`](oh-my-pi/config/WATCHDOG.yml), [`oh-my-pi/README.md`](oh-my-pi/README.md).

### 2. Jev Benchmark Lab Module (`jev-benchmark`)

The offline evaluation laboratory for measuring decision quality across real multi-hour developer sessions:

- **Compaction Replay Lab**: Replays real transcripts through context-compaction boundaries to measure where agent recall fails.
- **Laya Typed Decisions Runner**: Local CPU runner that executes typed recovery decisions against harvested developer turns without cloud API costs. Capped pilot completed 805/805 planned jobs over 7 of 80 streams.
- **Walkforward Harvest Datasets**: Pinned transcript fixtures and gold-standard evaluation turns covering Claude Code, Kilo, and oh-my-pi executions.
- **Comparative Reporting**: Automated HTML reports visualizing disagreement rates, decision latency, and cost comparisons between local CPU evaluation and hosted decision endpoints.
- **Key paths:** [`modules/coordination/jev-oss-compare/v0.1.0/`](modules/coordination/jev-oss-compare/v0.1.0/README.md), [`modules/coordination/jev-oss-compare/v0.1.0/fast-jev-compaction-lab/`](modules/coordination/jev-oss-compare/v0.1.0/fast-jev-compaction-lab/README.md), [`modules/coordination/jev-oss-compare/v0.1.0/scripts/laya_typed_decisions/v1/runner.py`](modules/coordination/jev-oss-compare/v0.1.0/scripts/laya_typed_decisions/v1/runner.py), [`modules/coordination/jev-oss-compare/v0.1.0/reports/runs/laya-pilot-20260929.json`](modules/coordination/jev-oss-compare/v0.1.0/reports/runs/laya-pilot-20260929.json).

### 3. Multi-Agent Hotloader Module (`multi-agent-hotload`)

The coordination runtime package designed to be installed into external working repositories:

- **Full PCM + Content Generation Coordination**: Wires Project Continuity Modules (continuity CLI 0.6.0 @ `4e23854…` with PR-only delivery, required CI gates, and auto-merge) together with full Content Generation Modules (pinned at 0.5.7 @ `c069613…` across all modules).
- **Prompt Injection Protocol (`PROMPT_INJECT.md`)**: Injects deterministic coordination constraints and role boundaries into subagents and fresh sessions.
- **Role Rosters (`ROLES.md`)**: Defines primary writer ownership, reviewer responsibilities, and verification roles across concurrent agents.
- **Installation Verifier (`hotload_check.py`)**: CLI validation script that verifies target repository checkouts, helper commit pins, and file structures.
- **Key paths:** [`modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md`](modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md), [`modules/coordination/multi-agent-hotload/v0.1.0/PROMPT_INJECT.md`](modules/coordination/multi-agent-hotload/v0.1.0/PROMPT_INJECT.md), [`modules/coordination/multi-agent-hotload/v0.1.0/ROLES.md`](modules/coordination/multi-agent-hotload/v0.1.0/ROLES.md), [`modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py`](modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py).

### Module Architecture Summary

| Module | Primary Role | Runtime Requirement | Key Surface | Status |
| --- | --- | --- | --- | --- |
| **`jev-omp`** | Live agent runtime defense & loop control | Node / Bun / TypeScript (`esbuild`) | [`oh-my-pi/extensions/`](oh-my-pi/extensions/) | Shipped (v2 court) |
| **`jev-benchmark`** | Offline transcript replay & decision scoring | Python 3.12 (CPU local or API) | [`modules/coordination/jev-oss-compare/`](modules/coordination/jev-oss-compare/v0.1.0/) | Active pilot (issue #28 open) |
| **`multi-agent-hotload`** | Cross-repo team coordination & helper wiring | Python / continuity CLI 0.6.0 | [`modules/coordination/multi-agent-hotload/`](modules/coordination/multi-agent-hotload/v0.1.0/) | Shipped (PR #12) |

## How it works

The system operates across three tightly integrated stages:

### Step 1: Decision Gates Intercept Proposals

Decision gates sit directly in front of agent actions. Each gate packages a minimal evaluation payload—the user's pinned constraints, recent tool outputs, and the proposed next action—and routes it through a fast decision classifier:

- **PreToolUse Gate (`jev-gate-pin`)**: Checks tool calls against pinned brief boundaries. A proposal to deploy self-hosted code when the brief demanded hosted APIs triggers an immediate `deny` and `rethink_plan` route.
- **Prompt Ambiguity Gate (`jev-ambiguity-gate`)**: Evaluates incoming prompts and session resumptions, requesting intent clarification before execution begins on ambiguous briefs.
- **Research Needed Gate (`jev-research-gate`)**: Detects high-consequence factual assertions made without primary documentation, enforcing a `research_more` recovery step.

### Step 2: Runtime Adjudication in `jev-omp`

In live sessions, background subagents and external analyzers regularly produce advisories. Without controls, these advisories trigger recursive interruptions:

1. An advisory arrives with a suggestion.
2. `jev-court.ts` verifies the session's remaining advisory budget and turn counter.
3. If the advisor attempts to steer on a settled decision, `loop-guard.ts` suppresses the interrupt, preventing runaway context growth.
4. When actionable drift is detected, the court issues a typed verdict instructing the agent to re-examine the user's brief.

### Step 3: Offline Replay and Benchmark in `jev-benchmark`

To ensure decision gates remain accurate without human babysitting, `jev-benchmark` replays recorded transcripts through the decision model:

1. Real session transcripts are stripped of secrets and ingested into [`session-ops-capture`](modules/coordination/session-ops-capture/v0.1.0/README.md).
2. The compaction lab simulates memory truncation to recreate the exact moment of failure.
3. The Laya decision runner evaluates whether the gate would have caught the drift, recording typed receipts in `reports/runs/`.

### Step 4: Hotload Installation in `multi-agent-hotload`

Target repositories install this full harness by referencing `HOTLOAD.md`. The target repo registers the coordination pack in its own configuration and runs `hotload_check.py` to ensure all continuity pins, role rosters, and writing guidelines are active without modifying upstream source code.

## Evidence and boundaries

ACS grounds every public claim in versioned repository artifacts, committed evaluation receipts, or direct external records:

| Claim | Source | Status | What this supports | What this leaves unproven |
| --- | --- | --- | --- | --- |
| **jev-court v2 stops advisory storms** | [`oh-my-pi/README.md`](oh-my-pi/README.md) | Shipped | Replay of 94-note `#35` fixture passes 38/38 assertions; reduces 83 injections to 0. | Disabled by default; harness async-result wake remains external; live multi-day session confirmation pending (#37). |
| **Local Laya CPU lane runs end-to-end** | [`laya-pilot-20260929.json`](modules/coordination/jev-oss-compare/v0.1.0/reports/runs/laya-pilot-20260929.json) | Experimentally supported | Completed 805/805 planned pilot jobs over 7 of 80 streams on local CPU. | Discovery-only on truncated export; uncalibrated confidence (ECE 0.213); full catch rate requires 81-file blind replay ([#28](https://github.com/Pukujan/agent-custom-setup/issues/28)). |
| **Tool gate denies unpermitted self-hosting** | [`jev-gate-pin README`](modules/coordination/jev-gate-pin/v0.1.0/README.md) | Shipped | Fish fixtures require `deny` on self-host proposal; zero false negatives required on block set. | Registered as draft/optional; live binding load-order across third-party harnesses is outside v0.1.0 scope. |
| **Hosted comparison decision endpoint exists** | [OpenRouter endpoint](https://openrouter.ai/api/v1/models/typesafe/jev-1.13/endpoints) | Shipped | Provider lists `typesafe/jev-1.13` text-to-decisions model at $0.042/M prompt tokens with no completion fee. | Third-party availability and pricing can change; not exercised in CI; provider claims are traceable, not verified by ACS. |
| **Multi-agent hotload pack installs full stack** | [`HOTLOAD.md`](modules/coordination/multi-agent-hotload/v0.1.0/HOTLOAD.md) | Shipped | Shipped via PR #12; pins PCM CLI 0.6.0 and Content Generation Modules; `hotload_check.py` validates target checkouts. | Does not guarantee adopter agents honor all prompt rules; dependent gates remain opt-in. |
| **Three-module separation across codebase** | [Issue #44](https://github.com/Pukujan/agent-custom-setup/issues/44) | Planned | Proposal to formally decouple `jev-omp`, `jev-benchmark`, and `multi-agent-hotload` directory trees and CI. | Under active design; paths remain linked at current repository locations until migration PR merges. |

### Operational Boundaries

- **No upstream replacement:** ACS does not replace Project Continuity Modules (PCM) or Content Generation Modules; it pins them as external authorities and does not vendor their source trees.
- **Advisory safety net:** Decision gates and `jev-court` are advisory seatbelts. Final project and code authority always belongs to the human operator.
- **Pilot vs. catch rate:** Benchmark pilot numbers are discovery-only sanity checks, not statistical guarantees of live detection rates.
- **Zero secrets in repository:** No API keys, credentials, session tokens, or `.env` files enter this repository. All external model and provider keys are referenced solely by environment variable name.
- **Visual assets:** Narrative marketing artwork remains deferred; the documentation uses a text-first contract with the official compact blue SVG mark (`assets/registry-icon.svg`).

## Try it

Verify the core mechanisms locally in three commands:

```bash
# 1. Test the Fish fixture gate: hosted-only brief denies self-host proposal
python3 modules/coordination/jev-gate-pin/v0.1.0/tests/test_fish_fixtures.py

# 2. Validate multi-agent hotload assignment pins against target repo
python3 modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py \
  --adopter-root . \
  --assignment modules/coordination/multi-agent-hotload/v0.1.0/examples/assignment.example.json \
  --skip-cgm-validate

# 3. Verify oh-my-pi watchdog and court extension configurations
python3 -c '
import yaml, json, glob
files = sorted(glob.glob("oh-my-pi/config/*.yml")) + sorted(glob.glob("oh-my-pi/config/*.json"))
for f in files:
    (json.load if f.endswith(".json") else yaml.safe_load)(open(f))
print(f"OK: {len(files)} config template(s) parsed successfully")
'
```
