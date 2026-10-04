# NOTES — multi-agent hotload v0.1.0

## Authority

- **ACS is source of truth** for this module. Desktop (or other) paths are deploy mirrors only.
- Sync direction after merge: **ACS → mirrors**.
- This pack is an **install surface**: agents loading the hot-loader must wire **FULL PCM + FULL CGM 0.5.12 + this runtime**. ACS does not replace PCM or CGM and must not vendor their source trees.
- **Binding:** ACS and all agent-hotloader adopters use the **complete** PCM and CGM stacks — not a slim subset (not HSW+writing-direction only, not hotload-only, not continuity-only PCM).

## Pins

| Dependency | Pin / note |
| --- | --- |
| PCM | `4e2385474b4af9249ca009cbdcb38c4498932475` · CLI **0.6.0** · protocol `0.1.0-draft`. Full stack ([adopter-enforcement](https://github.com/Pukujan/project-continuity-modules/blob/main/docs/adopter-enforcement.md)): continuity/checkpoints + GitHub issues own progression + PR-only + required CI gates + branch-protection/auto-merge preference + fail-closed + leaf/parent receipts. Still not the proposal layer. |
| CGM | `6831f91e165b62d719c05eb492f7375fa932b560` · **0.5.12**. Full eight modules: `brand-foundation`, `content-context`, `writing-direction`, `human-sounding-writing`, `visual-direction`, `image-generation`, `html-demo` + `human_output_contract` (README playbook/template/contract, quality PDD/SDD/TDD, provenance, WRITING_ROUTING, HSW guide/rules, scanability, claim-evidence). |

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

Branched from ACS policy / coordination-registry lineage (PR #10 / `POLICY.md` + `registry.json`). Full-stack pin tightening Refs #11 (Alex binding: full PCM + full CGM for ACS and adopters).

## Verify

```bash
export CGM_ROOT=/path/to/content-generation-modules  # HEAD must be 6831f91e… (0.5.12)
export ADOPTER_ROOT=/path/to/working-repo            # must include .content-system/
python modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py \
  --cgm-root "$CGM_ROOT" --adopter-root "$ADOPTER_ROOT"
# must print hotload_check: OK and cgm_validate=VALID
python -m pytest modules/coordination/multi-agent-hotload/v0.1.0/tests -q
```

After VALID: MUST load modules per CGM `docs/writing-routing.json` / `docs/ACS_VERIFY.md` (README→writing-direction; PR/issue/docs/commits/HTML reports/compare/appendable→hsw (default ON); basenames→hon); paste `acs_prompt_inject.system_block` at agent boot (always_on) (hotload_check writes `PROMPT_INJECT.md` and prints instruction). Validate does not enforce prose quality.
