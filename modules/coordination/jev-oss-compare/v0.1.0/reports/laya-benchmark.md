# Blind local replay

_Local replay · aggregate observations_

Baseline walk-forward decisions, auto-mode tool decisions, and upstream compaction are separate experiments. Correctness and recovered task outcomes remain unmeasured.

## Overview

| Observation                           | Count |
| ------------------------------------- | ----- |
| Current checks and aggregate receipts | 59    |
| Receipt lines and aggregate inputs    | 59    |
| Unsupported adapter rows omitted      | 0     |

## Validation and remaining coverage

| Validation                   | Status          |
| ---------------------------- | --------------- |
| Hidden whole-session holdout | Not implemented |
| M01–M14 metamorphic suite    | Unverified      |

_Supplied evidence metadata is shown as supplied; the renderer does not run validation. Existing reviewed runs cannot acquire hidden-holdout status retroactively._

| Requested baseline model | Availability          |
| ------------------------ | --------------------- |
| Laya                     | Receipts available    |
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

## Baseline walk-forward · Laya

- **Status**: Replay complete
- **Experiment**: 720d230fcb59
- **Profile**: 3d37a131e70c43a08a756dfe218c67077d615bf7662376ae3fe94e32699b0bde
- **Explicit limits**: Research excerpt outputs are separate from tool permission. Native compaction metadata does not establish semantic retention. Coverage and correctness are separate observations. Baseline context uses conversation/root/sidechain stream IDs. Task-level context IDs are not implemented. A stream may contain multiple tasks, so exhaustive pair checks can include cross-task comparisons. This is a scope caveat; individual decision correctness remains unmeasured.

### Recorded checks

| Recorded check                 | Current count |
| ------------------------------ | ------------- |
| Ack expectation not required   | 2             |
| Ack expectation required       | 4             |
| Ack expectation unclear        | 3             |
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
| Ack spans incomplete           | 5             |
| Ack spans missing response     | 2             |
| Ack spans not required         | 0             |
| Ack spans required             | 4             |
| Ack spans seen                 | 9             |
| Assistant plan boundaries      | 1             |
| Compact boundaries             | 0             |
| Fixed denies                   | 0             |
| Phase2 jobs                    | 8             |
| Pin id checks                  | 0             |
| Plan boundary incomplete       | 5             |
| Plan intent jobs               | 6             |
| Research boundaries            | 0             |
| Research incomplete boundaries | 0             |
| Research jobs                  | 0             |
| Semantic unknown               | 0             |
| Stream count                   | 1             |
| Tool calls                     | 0             |
| Tool pin jobs                  | 0             |
| Tool unpinned                  | 0             |
| Unresolved sidechain streams   | 0             |
| Recovery routes                | 32            |
| Assistant boundary             | 6             |
| User relations                 | 36            |
| Task context                   | 36            |
| Acknowledgment expectation     | 9             |
| Pin status                     | 9             |
| Acknowledgment response        | 2             |
| Plan intent                    | 6             |

### Route totals

| Gate            | Route            | Count |
| --------------- | ---------------- | ----- |
| Recovery routes | Escalate         | 24    |
| Recovery routes | Reconfirm intent | 8     |

### Decision counts

| Gate                       | Output                   | Count |
| -------------------------- | ------------------------ | ----- |
| Recovery routes            | Escalate                 | 24    |
| Recovery routes            | Reconfirm intent         | 8     |
| Assistant boundary         | Unclear                  | 5     |
| Assistant boundary         | Proposed plan            | 1     |
| User relations             | Revises or supersedes    | 1     |
| User relations             | Unrelated                | 2     |
| User relations             | Questions earlier intent | 1     |
| User relations             | Unclear                  | 8     |
| User relations             | Same topic               | 12    |
| User relations             | Supports                 | 6     |
| User relations             | Reopens or uncertain     | 2     |
| Task context               | Same task                | 20    |
| Task context               | New task                 | 13    |
| Task context               | Unclear                  | 3     |
| Acknowledgment expectation | Unclear                  | 3     |
| Acknowledgment expectation | Required                 | 4     |
| Acknowledgment expectation | Not required             | 2     |
| Pin status                 | Unclear                  | 3     |
| Pin status                 | Context                  | 3     |
| Pin status                 | Durable                  | 3     |
| Acknowledgment response    | Unclear                  | 1     |
| Acknowledgment response    | Partial                  | 1     |
| Plan intent                | Uncertain                | 6     |

### Attempts and cache activity

| Observation                      | Count |
| -------------------------------- | ----- |
| Receipt lines observed           | 59    |
| Current logical checks           | 59    |
| Retry rows superseded            | 0     |
| Exact duplicate rows excluded    | 0     |
| Explicit uncached model attempts | 59    |
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

| Score band         | Checks |
| ------------------ | ------ |
| Below 0.50         | 97     |
| 0.50 to below 0.75 | 7      |
| 0.75 to below 0.90 | 0      |
| 0.90 to 1.00       | 0      |

_OpenJev uses candidate-normalized top-20 scores. Provider semantics differ; these observations are uncalibrated and do not establish accuracy or a shared confidence threshold._

### Latency and timing

- **Timed checks**: 59 current uncached timed checks
- **Median latency (p50)**: 4752.66 ms
- **95th percentile latency (p95)**: unavailable ms
- **Cached timings excluded**: 0

---

Aggregate counts only. Message content, event identifiers, tool arguments, prompts, reference answers, diagnostic reasons, endpoint addresses, and arbitrary metadata are omitted.
