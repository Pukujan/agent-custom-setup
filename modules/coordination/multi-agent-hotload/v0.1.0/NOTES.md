# NOTES — multi-agent hotload v0.1.0

## Authority

- **ACS is source of truth** for this module. Desktop (or other) paths are deploy mirrors only.
- Sync direction after merge: **ACS → mirrors**.
- This pack is an **install surface**: agents loading the hot-loader must wire **PCM + CGM + this runtime**. ACS does not replace PCM or CGM and must not vendor their source trees.

## Pins

| Dependency | Pin / note |
| --- | --- |
| PCM | Reference checkout for continuity only |
| CGM | `c7d9c3f6b5b301d3a3bc89642d2f92fd08748979` (0.5.0). Re-pin **0.5.1** after CGM PR #17 merges. Modules: `human-sounding-writing`, `writing-direction` |

## Watchdog

- **Agent-less only** (cron / GitHub Action / `scripts/watchdog_check.py`).
- No secrets in workflow stubs; consuming repos supply their own `GITHUB_TOKEN` via Actions defaults if they enable the stub.
- Lease failover stays in **hours** (4–24). Watchdog interval stays in **minutes** (~10). Do not conflate them.

## Secrets

Never commit or print API keys, tokens, cookies, or `.env` contents. This module has no runtime secret files.

## Base lineage

Branched from ACS policy / multi-setup registry lineage (PR #10 / `POLICY.md` + `registry.json`). Extends the registry; does not replace InferHub or other modules.

## Verify

```bash
python modules/coordination/multi-agent-hotload/v0.1.0/scripts/hotload_check.py
python -m pytest modules/coordination/multi-agent-hotload/v0.1.0/tests -q
```
