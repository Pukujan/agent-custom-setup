# NOTES — multi-agent hotload v0.1.0

## Authority

- **ACS is source of truth** for this module. Desktop (or other) paths are deploy mirrors only.
- Sync direction after merge: **ACS → mirrors**.
- This pack is an **install surface**: agents loading the hot-loader must wire **FULL PCM + FULL CGM 0.5.1 + this runtime**. ACS does not replace PCM or CGM and must not vendor their source trees.
- **Binding:** ACS and all agent-hotloader adopters use the **complete** PCM and CGM stacks — not a slim subset (not HSW+writing-direction only, not hotload-only, not continuity-only PCM).

## Pins

| Dependency | Pin / note |
| --- | --- |
| PCM | `4e2385474b4af9249ca009cbdcb38c4498932475` · CLI **0.6.0** · protocol `0.1.0-draft`. Full stack: continuity/checkpoints + GitHub issues own progression + PR-only + required CI gates + branch-protection/auto-merge preference + fail-closed + leaf/parent receipts. Still not the proposal layer. |
| CGM | `9874b26dc46499137bf22e1ca163874ef2dd5e7a` · **0.5.1**. Full seven modules: `brand-foundation`, `content-context`, `writing-direction`, `human-sounding-writing`, `visual-direction`, `image-generation`, `html-demo` + `human_output_contract` (README playbook/template/contract, quality PDD/SDD/TDD, provenance, WRITING_ROUTING, HSW guide/rules, scanability, claim-evidence). |

Validate CGM adapters with:

```bash
python scripts/validate_content_system.py --root <cgm-checkout> --adapter <target>/.content-system --project-root <target>
```

## Boss lease + claim queue

- Lease failover is in **minutes** (default **30**; range **15–120** via `lease_ttl_minutes`).
- After vacancy, **GitHub-canonical `claim_queue`** is FIFO; front takes boss; returning boss joins at end.
- Zombie: re-read GitHub claim on wake; reject boss actions if not named; optional issue comment `lost lease → rejoining queue`; no out-of-band DM.
- Keep as-of history append-only.

## Watchdog

- **Agent-less only** (cron / GitHub Action / `scripts/watchdog_check.py`).
- No secrets in workflow stubs; consuming repos supply their own `GITHUB_TOKEN` via Actions defaults if they enable the stub.
- Watchdog interval stays in **minutes** (~10) for liveness/nudge only. Do not conflate with lease failover.

## Secrets

Never commit or print API keys, tokens, cookies, or `.env` contents. This module has no runtime secret files.

## Base lineage

Branched from ACS policy / multi-setup registry lineage (PR #10 / `POLICY.md` + `registry.json`). Extends the registry; does not replace InferHub or other modules. Full-stack pin tightening Refs #11 (Alex binding: full PCM + full CGM for ACS and adopters).

## Verify

```bash
python modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py
python -m pytest modules/coordination/multi-agent-hotload/v0.1.0/tests -q
```
