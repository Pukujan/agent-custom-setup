# Aggregate report for blind local replay

The report keeps three experiments separate: baseline walk-forward gates, the tool-only auto-mode adapter, and upstream fast-jev-compaction. It shows current decisions, receipt attempts, retry/cache activity, incomplete coverage, omitted/unsupported rows, requested model availability, and source gaps. Counts do not establish accuracy or recovered task outcomes.

The renderer reads private **content-free receipts only**. It never reads transcript sources, imports a replay runner, contacts a model, or alters a running replay. Message bodies, tool arguments, prompts, per-event identifiers, arbitrary metadata, diagnostic reasons, and reference answers are discarded. Fixed labels, numeric aggregates, and hashed fingerprints appear in the self-contained HTML.

## Commands

Create the empty report, labelled **Not run**:

```text
python modules/coordination/jev-oss-compare/v0.1.0/scripts/blind_replay_report.py
```

Render one run; the summary is optional:

```text
python modules/coordination/jev-oss-compare/v0.1.0/scripts/blind_replay_report.py --receipt-dir <private-run-directory> --run-id <frozen-run-id> --summary <content-free-summary.json>
```

Combine separate run directories and aggregate compaction receipts:

```text
python modules/coordination/jev-oss-compare/v0.1.0/scripts/blind_replay_report.py --receipt-dir <baseline-4b-run> --receipt-dir <baseline-9b-run> --receipt-dir <auto-mode-run> --compaction-receipt <compact-4b.json> --compaction-receipt <compact-9b.json> --report-context <content-free-report-context.json>
```

`--receipt-dir`, `--summary`, and `--compaction-receipt` can repeat. Each run directory contains `events.jsonl` directly or under lane directories. Mixed run IDs inside one directory are rejected; different supplied run directories remain separate experiments. `--run-id` is valid with one run directory. Summaries match by run ID, or by directory order when their counts match; a contradictory summary run ID is rejected. Compaction files must declare `adapter: fast-jev-compaction-openjev-local`. Every supplied JSON/JSONL row must declare `content_included: false`.

Output: `modules/coordination/jev-oss-compare/v0.1.0/reports/blind-local-replay.html`; use `--out` for another path. Refresh after complete receipt writes. The renderer performs no polling and requests no remote assets.

## Counting contracts and limits

| Input | Report treatment | Limit |
|---|---|---|
| Baseline JSONL | Final pin/relation/tool decisions separate from excerpt/group checks; `research_outcome` and shadow `research_route` are supported. | Research routes describe what the router would do; historical actions remain unchanged. Native compaction semantics remain unknown. |
| Auto-mode JSONL | `auto_mode_tool` reads `decision`, `probabilities`, and `latency_ms`; model/cache flags and deterministic policy bypasses are separate counts. | No pin relations or research gate; deterministic shell policy may bypass model judgment. |
| Compaction aggregate JSON | Numeric upstream stats, keep/drop counts, request timings, text fingerprint preservation, and whether context fitting was reported. | One normalized conversation per input; tool pruning is not historical compaction replay or semantic instruction retention. |

The baseline's context boundary is the conversation/root/sidechain stream ID. Task-level context IDs are not implemented. A stream may contain multiple tasks, so exhaustive user-message pair checks can include cross-task comparisons. Every baseline report section includes this fixed scope caveat; it does not claim that any particular decision was wrong.

Latest receipt wins for each stable run/adapter/lane/stream/event/gate/pair/chunk identity. Changed timings or a retry outcome do not inflate current decision counts. Earlier retries and exact duplicate rows remain separately counted. Rows lacking an event identity can only be deduplicated exactly; this limit is displayed. Model/cache attempt counts appear only where explicit flags exist; supplied run-summary counters are separately labelled and may describe one execution attempt.

Compaction aggregates with a valid `run_identity_sha256` can be deduplicated by frozen identity/source/model. Current upstream aggregate receipts lack that identity; differing aggregates cannot safely be treated as retries, and the page explicitly shows this limit. Exact duplicates are still excluded. Supply only one latest aggregate per conversation/run unless preserving separate experiments intentionally.

Unsupported adapters/gates, unknown statuses/decision labels, omitted evidence references, and excluded probability rows remain visible as counts. A supplied `complete` status cannot hide recognized incomplete or unsupported receipt rows. Pin coverage counts establish that all expected pin IDs were represented; they do not certify full character-span coverage. Timings describe current uncached receipts that include time; cached timings are excluded. OpenJev option scores are candidate-normalized top-20 scores, uncalibrated and different from provider confidence.

## Optional report context

Defaults list requested Laya/OpenJev 4B/OpenJev 9B/Kev 0.8B/4B/9B baseline lanes; absent lanes show **Not run / unavailable**. Claude source coverage defaults to **Unverified**, Grok to **Missing**. Hidden holdout defaults to **Not implemented**, and M01–M14 to **Unverified**. Running models or synthetic report tests do not change those defaults.

`--report-context` accepts this content-free metadata shape. Only fixed source/model/status labels, counts, and validated hashes are retained:

```json
{
  "content_included": false,
  "requested_models": ["laya", "openjev4", "openjev9", "kev08", "kev4", "kev9"],
  "sources": [
    {"source": "claude", "status": "available", "expected_events": 100, "observed_events": 100},
    {"source": "grok", "status": "missing"}
  ],
  "holdout": {"status": "not_implemented"},
  "metamorphic": {"status": "unverified"}
}
```

Evidence-backed holdout metadata additionally needs valid 64-character SHA-256 `evidence_sha256` and `split_manifest_sha256` values. Metamorphic metadata needs `evidence_sha256`; `status: passed` requires `passed: 14`, `failed: 0`, and `total: 14`. Without those fields the status stays unverified. Supplied statuses are explicitly labelled **supplied evidence metadata**: the renderer validates the shape, not the underlying experiment. A reviewed run cannot be relabelled as a hidden holdout retroactively.

### Exploratory partition recorded after inference

An optional `exploratory_partition` object creates its own section. It accepts only the exact fixed timing below, validated SHA-256 hashes, and nonnegative integer counts. The three root counts are required and must reconcile; `descendant_streams` and `source_manifest_sha256` are optional. Stream accounting supplies `development_streams`, `exploratory_streams`, and `quarantined_streams` together. When `total_streams` is supplied, those three counts must sum to it. Quarantined streams stay visible and are excluded from development/exploratory counts. Arbitrary labels, session identifiers, and reasons are discarded. Invalid timing, hashes, partial stream accounting, negative/non-integer counts, or inconsistent totals reject the input.

```json
{
  "content_included": false,
  "exploratory_partition": {
    "timing": "post-inference / pre-analysis exploratory partition",
    "partition_manifest_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "source_manifest_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "root_sessions": 14,
    "development_root_sessions": 10,
    "exploratory_root_sessions": 4,
    "descendant_streams": 66,
    "development_streams": 49,
    "exploratory_streams": 14,
    "quarantined_streams": 17,
    "total_streams": 80
  }
}
```

The counts/hashes above are synthetic examples. Supply the actual content-free partition metadata through `--report-context`. This records a **post-inference / pre-analysis exploratory partition** for exploratory analysis. It establishes neither hidden nor preregistered evaluation. Whenever this object is present, the report forces **Hidden whole-session holdout: Not implemented**, overriding even a supplied passing holdout claim with well-formed hashes.

## Verification

```text
python -m unittest discover -s modules/coordination/jev-oss-compare/v0.1.0/tests -p test_blind_replay_report.py -v
```

The suite uses synthetic receipts only. It checks privacy, stable retry identities, distinct chunks/pairs, auto-mode field mapping, compaction allowlists, unsupported rows, multiple run directories, missing lanes/sources, validation evidence boundaries, exploratory partition semantics, and incomplete-summary handling. Passing these report tests does **not** mean the benchmark's M01–M14 suite or holdout passed.

Before publishing, apply the module's CGM HSW check to this HTML path. A local artifact alone does not establish publication or a benchmark result.

Leaf: [issue #28](https://github.com/Pukujan/agent-custom-setup/issues/28); parent: none declared; related #25 and PR #26; dependencies: none for the renderer; task: ACS-0004. Primary writer: Codex; branch: `task/ACS-25-dual-jev-gates`.
