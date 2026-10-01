# NOTES

Owning issue #25 / PR #26. Policy patterns MIT from jomatsu/pi-jev-auto-mode.
Report path: `reports/jev-oss-compare.html`. Harvest from ACS session-ops fixtures.

## Multi-lane walk-forward (Refs #28)

- Primary gold: ACS Grok chat USER turns (`fixtures/acs_chat_gold/turns.json`); assistant never gold.
- Second stream: Claude full TX tools (hades + siblings; `--include-huge` default).
- Runner: `scripts/multi_lane_walkforward.py` â€” rolling pins, parallel L1â€“L5, live Jev only API, append existing `reports/jev-oss-compare.html`.
- Coverage gate fails if ACS gold narrow or Claude stream missing.
- Latest run: see `reports/runs/multi-lane-walkforward-latest.json`.

## Don't-pin gold (Refs #28)

- SERIAL RECONSIDER bursts (immediate why/arent/which after hasty claim) and DELAYED reconsider (15m/2hr wait-why): ambiguity hold; do NOT harden unify-DB pin; supersede on take-back.
- Harvested evidence: `fixtures/acs_chat_gold/harvested_serial_reconsider.json` (Claude TX human queued msgs; assistant never gold).
- Scoring: deny ideal; escalate counts as agree for hold-class; allow = FN.

