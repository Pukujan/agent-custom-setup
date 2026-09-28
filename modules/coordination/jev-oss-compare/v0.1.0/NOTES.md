# NOTES

Owning issue #25 / PR #26. Policy patterns MIT from jomatsu/pi-jev-auto-mode.
Report path: `reports/jev-oss-compare.html`. Harvest from ACS session-ops fixtures.

## Multi-lane walk-forward (Refs #28)

- Primary gold: ACS Grok chat USER turns (`fixtures/acs_chat_gold/turns.json`); assistant never gold.
- Second stream: Claude full TX tools (hades + siblings; `--include-huge` default).
- Runner: `scripts/multi_lane_walkforward.py` — rolling pins, parallel L1–L5, live Jev only API, append existing `reports/jev-oss-compare.html`.
- Coverage gate fails if ACS gold narrow or Claude stream missing.
- Latest run: see `reports/runs/multi-lane-walkforward-latest.json`.
