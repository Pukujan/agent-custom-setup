# Blind local replay

_Local replay · aggregate observations_

Baseline walk-forward decisions, auto-mode tool decisions, and upstream compaction are separate experiments. Correctness and recovered task outcomes remain unmeasured.

## Overview

| Observation                           | Count |
| ------------------------------------- | ----- |
| Current checks and aggregate receipts | 69    |
| Receipt lines and aggregate inputs    | 69    |
| Unsupported adapter rows omitted      | 0     |

## Validation and remaining coverage

| Validation                   | Status          |
| ---------------------------- | --------------- |
| Hidden whole-session holdout | Not implemented |
| M01–M14 metamorphic suite    | Unverified      |

_Supplied evidence metadata is shown as supplied; the renderer does not run validation. Existing reviewed runs cannot acquire hidden-holdout status retroactively._

| Requested baseline model | Availability          |
| ------------------------ | --------------------- |
| Laya                     | Not run / unavailable |
| OpenJev 4B               | Not run / unavailable |
| OpenJev 9B               | Not run / unavailable |
| Kev 0.8B                 | Not run / unavailable |
| Kev 4B                   | Not run / unavailable |
| Kev 9B                   | Not run / unavailable |

| Source | Status     | Observed events | Expected events |
| ------ | ---------- | --------------- | --------------- |
| Claude | Unverified | Unverified      | Unverified      |
| Grok   | Missing    | Unverified      | Unverified      |

## Scope and interpretation limits

Current decision counts use the latest receipt for each stable event/gate/chunk identity. Earlier retries and identical rows are counted separately. Rows without event identity can only be deduplicated exactly.

Research excerpts are supporting checks, not combined routing decisions. Pin ID coverage does not verify full character-span coverage. Timing is unavailable when receipts omit it. Native compaction metadata and tool-pruning ratios do not establish semantic retention.

## Jev typed-decision DAG · Jev 1.13

- **Status**: Replay complete
- **Experiment**: b1ba5cbd19b7
- **Profile**: c3bef2db64d9d9edf11bba51adf7b67243f59260ea9c0dda3379875323ed0909
- **Explicit limits**: Jev is a hosted System-1 decision model (TypeSafe, via OpenRouter) served through the same typed-decision DAG as the Laya lane. Route tallies are deduplicated to distinct event+route decisions, not per receipt row. Discovery-only: accuracy and catch-rate are not measured. Content-free counts only.

### Recorded checks

| Recorded check                 | Current count |
| ------------------------------ | ------------- |
| Ack expectation not required   | 9             |
| Ack expectation required       | 0             |
| Ack expectation unclear        | 0             |
| Assistant boundary incomplete  | 0             |
| Assistant boundary jobs        | 6             |
| Assistant boundary scored      | 6             |
| Expected message pairs         | 36            |
| Expected user event pairs      | 36            |
| Pin status incomplete          | 0             |
| Pin status jobs                | 9             |
| Pin status scored              | 9             |
| Relation job incomplete        | 0             |
| Relation job scored            | 36            |
| Relation jobs                  | 36            |
| Ack response jobs              | 2             |
| Ack spans incomplete           | 4             |
| Ack spans missing response     | 1             |
| Ack spans not required         | 2             |
| Ack spans required             | 3             |
| Ack spans seen                 | 9             |
| Assistant plan boundaries      | 5             |
| Compact boundaries             | 0             |
| Fixed denies                   | 0             |
| Phase2 jobs                    | 18            |
| Pin id checks                  | 0             |
| Plan boundary incomplete       | 0             |
| Plan intent jobs               | 16            |
| Research boundaries            | 6             |
| Research incomplete boundaries | 0             |
| Research jobs                  | 0             |
| Semantic unknown               | 0             |
| Stream count                   | 1             |
| Tool calls                     | 0             |
| Tool pin jobs                  | 0             |
| Tool unpinned                  | 0             |
| Unresolved sidechain streams   | 0             |
| Recovery routes                | 17            |
| User relations                 | 36            |
| Task context                   | 36            |
| Acknowledgment expectation     | 9             |
| Pin status                     | 9             |
| Assistant boundary             | 6             |
| Plan intent                    | 16            |
| Acknowledgment response        | 2             |

### Route totals

| Gate            | Route             | Count |
| --------------- | ----------------- | ----- |
| Recovery routes | Escalate          | 9     |
| Recovery routes | Reconfirm intent  | 3     |
| Recovery routes | Dispatch verifier | 5     |

### Decision counts

| Gate                       | Output                   | Count |
| -------------------------- | ------------------------ | ----- |
| Recovery routes            | Escalate                 | 9     |
| Recovery routes            | Reconfirm intent         | 3     |
| Recovery routes            | Dispatch verifier        | 5     |
| User relations             | Supports                 | 4     |
| User relations             | Unclear                  | 8     |
| User relations             | Unrelated                | 15    |
| User relations             | Questions earlier intent | 5     |
| User relations             | Same topic               | 2     |
| User relations             | Revises or supersedes    | 2     |
| Task context               | Same task                | 7     |
| Task context               | Unclear                  | 28    |
| Task context               | New task                 | 1     |
| Acknowledgment expectation | Not required             | 9     |
| Pin status                 | Unclear                  | 4     |
| Pin status                 | Durable                  | 3     |
| Pin status                 | Context                  | 1     |
| Pin status                 | Question                 | 1     |
| Assistant boundary         | Factual claim            | 1     |
| Assistant boundary         | Plan and claim           | 5     |
| Plan intent                | Irrelevant               | 13    |
| Plan intent                | Uncertain                | 3     |
| Acknowledgment response    | Omitted                  | 2     |

### Attempts and cache activity

| Observation                      | Count |
| -------------------------------- | ----- |
| Receipt lines observed           | 69    |
| Current logical checks           | 69    |
| Retry rows superseded            | 0     |
| Exact duplicate rows excluded    | 0     |
| Explicit uncached model attempts | 69    |
| Explicit cache attempts          | 0     |

### Coverage and omissions

| Observation                                                  | Count |
| ------------------------------------------------------------ | ----- |
| Incomplete checks or abstentions                             | 0     |
| Tool decisions with all pin IDs represented                  | 0     |
| Tool decisions with incomplete pin IDs                       | 0     |
| Hard-deny bypasses of pin judgment                           | 0     |
| Auto-mode deterministic policy bypasses                      | 0     |
| Omitted evidence references                                  | 0     |
| Native compaction boundaries with unknown semantic retention | 0     |
| Unsupported gate rows                                        | 0     |
| Unknown status rows                                          | 0     |
| Unrecognized decision labels omitted                         | 0     |
| Rows lacking logical event identity                          | 0     |
| Probability rows excluded                                    | 0     |

### Reported option scores

| Score band         | Jev option probabilities |
| ------------------ | ------------------------ |
| Below 0.50         | 63                       |
| 0.50 to below 0.75 | 37                       |
| 0.75 to below 0.90 | 5                        |
| 0.90 to 1.00       | 9                        |

_One band per answered question (the hosted model's probability for its chosen option). Provider semantics differ; these are model-defined, not a calibrated correctness or a shared confidence threshold._

### Latency and timing

- **Timed checks**: 69 current uncached timed checks
- **Median latency (p50)**: 238.28 ms
- **95th percentile latency (p95)**: 430.66 ms
- **Cached timings excluded**: 0

---

Aggregate counts only. Message content, event identifiers, tool arguments, prompts, reference answers, diagnostic reasons, endpoint addresses, and arbitrary metadata are omitted.
