#!/usr/bin/env python3
"""Render content-free replay receipts. Never imports runners or model clients."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping

DEFAULT_REPORT = Path(__file__).resolve().parents[1] / "reports" / "blind-local-replay.html"
DEFAULT_MD_REPORT = Path(__file__).resolve().parents[1] / "reports" / "laya-benchmark.md"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
SHA256 = re.compile(r"[a-fA-F0-9]{64}\Z")
STATUSES = frozenset({"scored", "aggregated", "scored_chunk", "scored_empty", "incomplete", "abstained"})
RUN_STATUSES = frozenset({"not_run", "planned", "running", "complete", "incomplete", "failed_closed"})
ADAPTERS = {"baseline": "Baseline walk-forward", "auto_mode": "Auto-mode tool adapter",
            "compaction": "Fast-jev-compaction adapter"}
ADAPTERS["laya_dag"] = "Laya typed-decision DAG"
ADAPTERS["jev"] = "Jev typed-decision DAG"
LIMITS = {
    "baseline": "Research excerpt outputs are separate from tool permission. Native compaction metadata does not establish semantic retention. Coverage and correctness are separate observations. Baseline context uses conversation/root/sidechain stream IDs. Task-level context IDs are not implemented. A stream may contain multiple tasks, so exhaustive pair checks can include cross-task comparisons. This is a scope caveat; individual decision correctness remains unmeasured.",
    "auto_mode": "Tool-only replay using prior user history. No user pin/relation or research gate. Deterministic shell policy may bypass model judgment; oversized context escalates.",
    "compaction": "One normalized conversation per receipt, not replay at every historical boundary. Tool call/result pruning and unchanged user/assistant text do not establish semantic instruction retention. Upstream context fitting may omit history.",
}
LIMITS["laya_dag"] = ("Laya is a specialist typed-decision checkpoint fine-tuned on four synthetic workflows, not coding-agent "
                      "transcripts. Scores are model-defined and uncalibrated; routes are recovery suggestions, not measured "
                      "correctness, catch-rate, or generalization. Content-free counts only.")
LIMITS["jev"] = ("Jev is a hosted System-1 decision model (TypeSafe, via OpenRouter) served through the same typed-decision DAG "
                 "as the Laya lane. Route tallies are deduplicated to distinct event+route decisions, not per receipt row. "
                 "Discovery-only: accuracy and catch-rate are not measured. Content-free counts only.")
GATE_LABELS = {
    "user_pin": "User pins", "user_relation": "User relationships", "research": "Research excerpts",
    "research_aggregate": "Research boundary decisions", "research_outcome": "Research boundary outcomes", "research_route": "Research shadow routes",
    "tool": "Tool decisions", "compaction": "Native compaction boundaries",
    "user_pin_chunk": "Pin excerpts", "user_relation_chunk": "Relationship excerpts",
    "tool_pin_group": "Pin groups", "tool_pin_diagnostic": "Pin checks", "stream": "Stream checks",
    "auto_mode_tool": "Auto-mode tool decisions",
    "pin_status": "Pin status", "relation": "User relations", "task_context": "Task context",
    "plan_intent": "Plan intent", "assistant_boundary": "Assistant boundary",
    "ack_expectation": "Acknowledgment expectation", "acknowledgment_response": "Acknowledgment response",
    "laya_route": "Recovery routes",
}
CHOICES = {
    "user_pin": {"durable_assertion": "Durable", "tentative_or_reconsidering": "Tentative or reconsidering",
                 "question_only": "Question", "context_only": "Context", "unclear": "Unclear"},
    "user_relation": {"unrelated": "Unrelated", "same_topic": "Same topic",
                      "asks_about_or_questions": "Questions earlier intent", "adds_constraint_or_refinement": "Refines",
                      "supports_or_commits": "Supports", "revises_or_supersedes": "Revises or supersedes",
                      "reopens_or_uncertain": "Reopens or uncertain", "conflicts": "Conflicts", "unclear": "Unclear"},
    "research": {"ready": "Ready", "research_more": "Research more", "insufficient": "Insufficient"},
    "tool": {"allow": "Allow", "deny": "Deny", "escalate": "Escalate"},
}
CHOICES["auto_mode_tool"] = CHOICES["tool"]
CHOICES["research_aggregate"] = CHOICES["research"]
CHOICES["research_outcome"] = {**CHOICES["research"], "incomplete": "Incomplete"}
CHOICES["research_route"] = {"go": "Go", "loop": "Loop", "hold": "Hold"}
CHOICES["laya_route"] = {"reconfirm_intent": "Reconfirm intent", "rethink_plan": "Rethink plan",
                         "research_more": "Research more", "dispatch_verifier": "Dispatch verifier",
                         "escalate": "Escalate", "proceed": "Proceed"}
CHOICES["pin_status"] = CHOICES["user_pin"]
CHOICES["relation"] = CHOICES["user_relation"]
CHOICES["task_context"] = {"same_task": "Same task", "new_task": "New task", "unclear": "Unclear"}
CHOICES["plan_intent"] = {"consistent": "Consistent", "conflict": "Conflict", "conflicts": "Conflicts",
                          "irrelevant": "Irrelevant", "uncertain": "Uncertain"}
CHOICES["assistant_boundary"] = {"factual_claim": "Factual claim", "proposed_plan": "Proposed plan",
                                  "plan_and_claim": "Plan and claim", "other": "Other", "unclear": "Unclear"}
CHOICES["ack_expectation"] = {"required": "Required", "not_required": "Not required", "unclear": "Unclear"}
CHOICES["acknowledgment_response"] = {"accurate": "Accurate", "partial": "Partial", "omitted": "Omitted",
                                       "contradicted": "Contradicted", "unclear": "Unclear"}
KNOWN_CHOICES = frozenset(choice for choices in CHOICES.values() for choice in choices)
PROBABILITY_BINS = ("Below 0.50", "0.50 to below 0.75", "0.75 to below 0.90", "0.90 to 1.00")
MODEL_LABELS = {"laya": "Laya", "jev": "Jev 1.13", "openjev4": "OpenJev 4B", "openjev9": "OpenJev 9B",
                "kev08": "Kev 0.8B", "kev4": "Kev 4B", "kev9": "Kev 9B", "local": "Local model"}
REQUESTED_MODELS = ("laya", "openjev4", "openjev9", "kev08", "kev4", "kev9")
EXPLORATORY_TIMING = "post-inference / pre-analysis exploratory partition"
PARTITION_COUNTS = {"root_sessions": "Total root sessions",
    "development_root_sessions": "Development root sessions",
    "exploratory_root_sessions": "Exploratory root sessions", "descendant_streams": "Grouped descendant streams",
    "development_streams": "Development streams", "exploratory_streams": "Exploratory streams",
    "quarantined_streams": "Quarantined streams", "total_streams": "Total streams"}
COMPACTION_STATS = {"messagesBefore": "Messages before", "messagesAfter": "Messages after",
    "charsBefore": "Characters before", "charsAfter": "Characters after", "calls": "Candidate calls",
    "kept": "Calls kept", "resultsDropped": "Results dropped", "callsDropped": "Calls dropped",
    "pinned": "Upstream pinned calls", "stateTokens": "Estimated state tokens", "requests": "Upstream batches", "ms": "Total elapsed milliseconds"}


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _finite(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
        return float(value)
    return None


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError("invalid_report_identifier")
    return value


def _hash(value: Any) -> str | None:
    return value.lower() if isinstance(value, str) and SHA256.fullmatch(value) else None


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _model_key(value: Any, lane_id: Any = None) -> str:
    name = str(value or "").lower()
    lane = str(lane_id or "").lower()
    # Some adapters return a generic backend model_id. Only map those when
    # the separately recorded lane names the requested checkpoint explicitly.
    if name == "typed-decisions" and lane == "laya-typed-decisions":
        return "laya"
    if name == "kev-latest" and lane == "kev-0.8b":
        return "kev08"
    if "laya" in name:
        return "laya"
    if "typesafe/jev" in name or ("jev" in name and "openjev" not in name and "kev" not in name):
        return "jev"
    if "openjev" in name or "open-jev" in name:
        return "openjev9" if "9b" in name else "openjev4" if "4b" in name else "local"
    if "kev" in name:
        return "kev08" if "0.8b" in name else "kev9" if "9b" in name else "kev4" if "4b" in name else "local"
    return "local"


def _percentile(values: list[float], proportion: float) -> float | None:
    return round(sorted(values)[math.ceil((len(values) - 1) * proportion)], 2) if values else None


def _adapter(row: Mapping[str, Any]) -> str | None:
    if row.get("gate") == "auto_mode_tool" and row.get("adapter") in {
            None, "auto-mode-openjev-local-v1", "auto-mode-openjev-local-v2"}:
        return "auto_mode"
    if row.get("adapter") in {None, "baseline"}:
        return "baseline"
    return None


def _summary_adapter(summary: Mapping[str, Any]) -> str:
    """Laya summaries must not be framed as a Baseline walk-forward lane."""
    adapter_id = str(summary.get("adapter_id", summary.get("adapter", ""))).lower()
    if adapter_id.startswith("laya-typed"):
        return "laya_dag"
    if adapter_id.startswith("jev-typed"):
        return "jev"
    return _adapter({"adapter": adapter_id or "baseline",
                     "gate": "auto_mode_tool" if "auto" in adapter_id else "baseline"}) or "baseline"



def _score_meta(lane: Mapping[str, Any]) -> tuple[str, str]:
    """(column label, caveat) for the reported-score band, keyed to the lane model."""
    if lane.get("model_key") == "laya" or lane.get("adapter") == "laya_dag":
        return ("Laya answer scores",
                "Laya records each chosen option's probability (answer_confidence). The checkpoint "
                "ships temperatures inherited from the base model, so these bands are uncalibrated "
                "and do not establish accuracy or a shared confidence threshold.")
    return ("Checks",
            "OpenJev uses candidate-normalized top-20 scores. Provider semantics differ; these "
            "observations are uncalibrated and do not establish accuracy or a shared confidence threshold.")
def _logical_key(row: Mapping[str, Any], adapter: str) -> tuple[str, bool]:
    """Private IDs distinguish decisions; no ID or source text is returned."""
    if not isinstance(row.get("event_id"), str) or not row["event_id"]:
        return _digest(row), False
    fields = ("run_id", "lane_id", "model_id", "run_identity_sha256", "stream_id_sha256", "event_id", "gate",
              "prior_event_id", "pin_event_id", "chunk_index", "current_chunk_index", "prior_chunk_index",
              "claim_chunk_index", "claim_char_span", "tool_chunk_index", "group_index", "tool_char_span",
              "pin_char_span", "char_span", "evidence_ids", "pin_chunks")
    return _digest([adapter, {key: row[key] for key in fields if key in row}]), True


def _choice(row: Mapping[str, Any], gate: str) -> Any:
    if gate == "auto_mode_tool":
        return row.get("decision")
    if gate == "tool":
        return row.get("verdict")
    if gate == "research_outcome":
        return row.get("outcome")
    if gate == "research_route":
        return row.get("route")
    return row.get("choice")


def _new_lane(row: Mapping[str, Any], adapter: str, summary: Mapping[str, Any]) -> dict[str, Any]:
    model = _model_key(row.get("model_id"), row.get("lane_id"))
    identity = _hash(row.get("run_identity_sha256"))
    return {"label": MODEL_LABELS[model], "model_key": model, "adapter": adapter,
        "fingerprint": (identity or _digest([row.get("lane_id"), row.get("model_id"), adapter]))[:12],
        "fingerprint_kind": "Run identity" if identity else "Lane fingerprint",
        "rows": 0, "attempt_rows": 0, "exact_duplicate_rows": 0, "retry_rows": 0,
        "unsupported_rows": 0, "unknown_status_rows": 0, "unknown_choice_rows": 0, "identity_unavailable_rows": 0,
        "model_attempts": 0, "cache_attempts": 0, "attempt_metadata_rows": 0, "policy_bypasses": 0,
        "gates": Counter(), "statuses": Counter(), "choices": {}, "elapsed": [], "cached_elapsed": [],
        "incomplete_checks": 0, "hard_denies": 0, "pin_coverage_complete": 0, "pin_coverage_incomplete": 0,
        "pin_coverage_bypassed": 0, "omitted_evidence_refs": 0, "compaction_semantics_unknown": 0,
        "answer_probability_bins": Counter(), "invalid_probability_rows": 0, "summary": summary}


def aggregate_receipts(paths: Iterable[Path], *, run_id: str | None = None,
                       run_summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One run, possibly multiple adapters. Latest logical receipt wins; attempts remain counted."""
    requested_id = _identifier(run_id) if run_id is not None else None
    summary = run_summary or {}
    summaries = {item["lane_id"]: item for item in summary.get("lane_results", [])
                 if isinstance(item, dict) and isinstance(item.get("lane_id"), str)}
    if isinstance(summary.get("lane_id"), str):
        summaries[summary["lane_id"]] = summary
    lanes: dict[str, dict[str, Any]] = {}
    latest: dict[str, tuple[dict[str, Any], str]] = {}
    seen_rows: set[str] = set()
    unsupported = 0
    for path in sorted(paths, key=lambda item: str(item)):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict) or row.get("content_included") is not False:
                    raise ValueError("content_free_receipt_required")
                current_id = _identifier(row.get("run_id"))
                requested_id = requested_id or current_id
                if current_id != requested_id:
                    raise ValueError("mixed_run_receipts")
                adapter = _adapter(row)
                if adapter is None:
                    unsupported += 1
                    continue
                lane_id = str(row.get("lane_id", ""))
                key = _digest([adapter, lane_id, row.get("model_id"), row.get("run_identity_sha256")])
                lane = lanes.setdefault(key, _new_lane(row, adapter, summaries.get(lane_id, {})))
                lane["attempt_rows"] += 1
                fingerprint = _digest(row)
                if fingerprint in seen_rows:
                    lane["exact_duplicate_rows"] += 1
                    continue
                seen_rows.add(fingerprint)
                if isinstance(row.get("model_called"), bool) or isinstance(row.get("cache_hit"), bool):
                    lane["attempt_metadata_rows"] += 1
                if row.get("model_cache_hit") is True or row.get("cache_hit") is True:
                    lane["cache_attempts"] += 1
                elif row.get("model_called") is True:
                    lane["model_attempts"] += 1
                logical_key, identity_available = _logical_key(row, adapter)
                if not identity_available:
                    lane["identity_unavailable_rows"] += 1
                if logical_key in latest:
                    lane["retry_rows"] += 1
                latest[logical_key] = (row, key)
    for row, key in latest.values():
        lane = lanes[key]
        lane["rows"] += 1
        gate, status = row.get("gate"), row.get("status")
        if gate not in GATE_LABELS:
            lane["unsupported_rows"] += 1
            continue
        lane["gates"][gate] += 1
        if status in STATUSES:
            lane["statuses"][status] += 1
        else:
            lane["unknown_status_rows"] += 1
        if status in {"incomplete", "abstained"}:
            lane["incomplete_checks"] += 1
        choice = _choice(row, gate)
        if gate in CHOICES:
            if choice in CHOICES[gate]:
                lane["choices"].setdefault(gate, Counter())[choice] += 1
            else:
                lane["unknown_choice_rows"] += 1
        elapsed = _finite(row.get("latency_ms") if gate == "auto_mode_tool" else row.get("elapsed_ms"))
        cached = row.get("model_cache_hit") is True or row.get("cache_hit") is True
        if elapsed is not None:
            lane["cached_elapsed" if cached else "elapsed"].append(elapsed)
        scores = row.get("probabilities") if gate == "auto_mode_tool" else row.get("scores")
        if scores:
            probabilities = [_finite(value) for value in scores.values()] if isinstance(scores, dict) else []
            valid = (isinstance(scores, dict) and bool(scores) and set(scores) <= KNOWN_CHOICES
                     and all(value is not None and value <= 1 for value in probabilities)
                     and .98 <= sum(probabilities) <= 1.02 and row.get("distribution_complete") is not False)
            probability = _finite(scores.get(choice)) if valid and choice in KNOWN_CHOICES else None
            if probability is not None:
                index = 0 if probability < .5 else 1 if probability < .75 else 2 if probability < .9 else 3
                lane["answer_probability_bins"][PROBABILITY_BINS[index]] += 1
            else:
                lane["invalid_probability_rows"] += 1
        if gate == "auto_mode_tool" and row.get("model_called") is False and status == "scored":
            lane["policy_bypasses"] += 1
        if gate == "tool":
            if row.get("fixed_deny_rule"):
                lane["hard_denies"] += 1
                lane["pin_coverage_bypassed"] += 1
            else:
                expected, groups = row.get("expected_pin_ids"), row.get("pin_groups")
                if isinstance(expected, list) and isinstance(groups, list):
                    covered = {item for group in groups if isinstance(group, dict)
                               for item in group.get("pin_ids", []) if isinstance(item, str)}
                    complete = all(isinstance(item, str) for item in expected) and set(expected) == covered and status == "scored"
                    lane["pin_coverage_complete" if complete else "pin_coverage_incomplete"] += 1
        omitted = row.get("omitted_evidence_ids")
        if isinstance(omitted, list):
            lane["omitted_evidence_refs"] += len(omitted)
        if gate == "compaction" and row.get("semantic_status") == "unknown":
            lane["compaction_semantics_unknown"] += 1
    rendered_lanes = []
    for key in sorted(lanes):
        lane = lanes[key]
        item = {name: value for name, value in lane.items() if name not in {"elapsed", "cached_elapsed", "summary"}}
        item.update(latency_p50_ms=_percentile(lane["elapsed"], .50), latency_p95_ms=_percentile(lane["elapsed"], .95),
                    timed_checks=len(lane["elapsed"]), cached_timed_checks=len(lane["cached_elapsed"]))
        supplied = lane["summary"]
        item["execution"] = {name: value for name in ("inference_requests", "decision_calls", "cache_hits", "incomplete_count", "model_calls")
                             if (value := _count(supplied.get(name))) is not None}
        supplied_status = supplied.get("status")
        problematic = any(item[name] for name in ("incomplete_checks", "unsupported_rows", "unknown_status_rows", "unknown_choice_rows"))
        item["status"] = "incomplete" if problematic or _count(supplied.get("incomplete_count")) else (
            supplied_status if supplied_status in RUN_STATUSES else "running")
        rendered_lanes.append(item)
    status = summary.get("status")
    if status not in RUN_STATUSES:
        status = "running" if rendered_lanes or unsupported else "not_run"
    if not rendered_lanes and not unsupported and status != "planned":
        status = "not_run"
    elif unsupported or any(item["status"] in {"incomplete", "failed_closed"} for item in rendered_lanes):
        status = "incomplete"
    return {"schema_version": 2, "status": status, "run_id": requested_id,
            "content_included": False, "lane_count": len(rendered_lanes), "unsupported_rows": unsupported,
            "receipt_rows": sum(item["rows"] for item in rendered_lanes),
            "attempt_rows": sum(item["attempt_rows"] for item in rendered_lanes) + unsupported, "lanes": rendered_lanes}


def aggregate_compaction(paths: Iterable[Path]) -> dict[str, Any]:
    latest: dict[str, dict[str, Any]] = {}
    attempts = duplicates = unsupported = 0
    seen: set[str] = set()
    for path in paths:
        row = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(row, dict) or row.get("content_included") is not False:
            raise ValueError("content_free_receipt_required")
        attempts += 1
        if row.get("adapter") != "fast-jev-compaction-openjev-local":
            unsupported += 1
            continue
        fingerprint = _digest(row)
        if fingerprint in seen:
            duplicates += 1
            continue
        seen.add(fingerprint)
        model = row.get("model") if isinstance(row.get("model"), dict) else {}
        identity = _hash(row.get("run_identity_sha256"))
        # Upstream receipts lack frozen config identity. Do not merge differing
        # aggregate values as retries merely because source/model match.
        key = _digest([identity, row.get("source_sha256"), model.get("digest")]) if identity else fingerprint
        compaction = row.get("compaction") if isinstance(row.get("compaction"), dict) else {}
        stats = compaction.get("stats") if isinstance(compaction.get("stats"), dict) else {}
        numeric = {name: value for name in COMPACTION_STATS if (value := _finite(stats.get(name))) is not None}
        preservation = row.get("content_preservation") if isinstance(row.get("content_preservation"), dict) else {}
        timings = compaction.get("openjev_latency_ms") if isinstance(compaction.get("openjev_latency_ms"), dict) else {}
        latest[key] = {"adapter": "compaction", "label": MODEL_LABELS[_model_key(model.get("name"))],
            "model_key": _model_key(model.get("name")), "fingerprint": key[:12],
            "status": row.get("status") if row.get("status") in RUN_STATUSES else "incomplete",
            "config_identity_available": identity is not None, "stats": numeric,
            "text_unchanged": preservation.get("unchanged") if isinstance(preservation.get("unchanged"), bool) else None,
            "actions": {name: value for name in ("keep", "drop_result", "drop_call")
                        if (value := _count(compaction.get("decision_action_counts", {}).get(name))) is not None},
            "requests": _count(compaction.get("openjev_requests")),
            "validated_responses": _count(compaction.get("openjev_responses_validated")),
            "latency_p50_ms": _finite(timings.get("median")), "latency_p95_ms": _finite(timings.get("p95")),
            "state_fitting_reported": isinstance(stats.get("stateStage"), str) and bool(stats["stateStage"]),
            "reduction_ratio": _finite(compaction.get("reduction_ratio"))}
    return {"receipts": list(latest.values()), "attempt_rows": attempts, "exact_duplicate_rows": duplicates,
            "unsupported_rows": unsupported}


def _validation(value: Any, kind: str) -> dict[str, Any]:
    default = "not_implemented" if kind == "holdout" else "unverified"
    if not isinstance(value, dict) or not _hash(value.get("evidence_sha256")):
        return {"status": default}
    if kind == "holdout" and not _hash(value.get("split_manifest_sha256")):
        return {"status": "unverified"}
    status = value.get("status")
    result = {"status": status if status in {"passed", "failed", "unverified", "not_implemented"} else "unverified",
              "evidence_supplied": True, "evidence_sha256": _hash(value["evidence_sha256"])}
    if kind == "metamorphic":
        result.update({name: count for name in ("passed", "failed", "total") if (count := _count(value.get(name))) is not None})
        if status == "passed" and (result.get("passed") != 14 or result.get("total") != 14 or result.get("failed") != 0):
            result["status"] = "unverified"
    return result


def _exploratory_partition(value: Any) -> dict[str, Any] | None:
    """Only fixed timing, validated hashes and counts; never labels or session IDs."""
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("timing") != EXPLORATORY_TIMING:
        raise ValueError("exploratory_partition_timing_invalid")
    manifest_hash = _hash(value.get("partition_manifest_sha256"))
    if manifest_hash is None:
        raise ValueError("exploratory_partition_hash_required")
    if any(name in value and _count(value[name]) is None for name in PARTITION_COUNTS):
        raise ValueError("exploratory_partition_counts_invalid")
    counts = {name: count for name in PARTITION_COUNTS if (count := _count(value.get(name))) is not None}
    required = {"root_sessions", "development_root_sessions", "exploratory_root_sessions"}
    if not required <= counts.keys() or counts["development_root_sessions"] + counts["exploratory_root_sessions"] != counts["root_sessions"]:
        raise ValueError("exploratory_partition_counts_invalid")
    stream_fields = {"development_streams", "exploratory_streams", "quarantined_streams"}
    if (stream_fields & counts.keys() or "total_streams" in counts) and not stream_fields <= counts.keys():
        raise ValueError("exploratory_partition_stream_counts_incomplete")
    if "total_streams" in counts and sum(counts[name] for name in stream_fields) != counts["total_streams"]:
        raise ValueError("exploratory_partition_stream_counts_mismatch")
    result = {"timing": EXPLORATORY_TIMING, "partition_manifest_sha256": manifest_hash, **counts}
    if "source_manifest_sha256" in value:
        source_hash = _hash(value["source_manifest_sha256"])
        if source_hash is None:
            raise ValueError("exploratory_source_hash_invalid")
        result["source_manifest_sha256"] = source_hash
    return result


def aggregate_experiments(experiments: list[dict[str, Any]], compaction: dict[str, Any] | None = None,
                          context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    compaction = compaction or {"receipts": [], "attempt_rows": 0, "exact_duplicate_rows": 0, "unsupported_rows": 0}
    lanes = [{**lane, "experiment_fingerprint": _digest(experiment.get("run_id"))[:12]}
             for experiment in experiments for lane in experiment["lanes"]]
    observed = {lane["model_key"] for lane in lanes if lane["adapter"] == "baseline"}
    requested = context.get("requested_models", REQUESTED_MODELS)
    if not isinstance(requested, list) and not isinstance(requested, tuple):
        requested = REQUESTED_MODELS
    roster = [{"label": MODEL_LABELS[key], "status": "Receipts available" if key in observed else "Not run / unavailable"}
              for key in requested if key in REQUESTED_MODELS]
    sources = []
    supplied_sources = {row.get("source"): row for row in context.get("sources", []) if isinstance(row, dict)}
    for key, label in (("claude", "Claude"), ("grok", "Grok")):
        source = supplied_sources.get(key, {})
        status = source.get("status")
        status = status if status in {"available", "missing", "incomplete", "unverified"} else "unverified" if key == "claude" else "missing"
        sources.append({"label": label, "status": status, **{name: count for name in ("expected_events", "observed_events")
                        if (count := _count(source.get(name))) is not None}})
    partition = _exploratory_partition(context.get("exploratory_partition"))
    validation = {kind: _validation(context.get(kind), kind) for kind in ("holdout", "metamorphic")}
    if partition is not None:
        # A post-inference partition must never inherit a supplied hidden-
        # holdout claim, even when that claim includes well-formed hashes.
        validation["holdout"] = {"status": "not_implemented"}
    return {"schema_version": 2, "content_included": False, "experiments": experiments,
        "lanes": lanes, "compaction": compaction, "roster": roster, "sources": sources,
        "validation": validation, "exploratory_partition": partition,
        "receipt_rows": sum(experiment["receipt_rows"] for experiment in experiments) + len(compaction["receipts"]),
        "attempt_rows": sum(experiment["attempt_rows"] for experiment in experiments) + compaction["attempt_rows"],
        "unsupported_rows": sum(experiment["unsupported_rows"] for experiment in experiments) + compaction["unsupported_rows"]}


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    escape = lambda value: html.escape(str(value))
    return ('<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th>{escape(value)}</th>' for value in headers)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{escape(value)}</td>' for value in row)
            + '</tr>' for row in rows) + '</tbody></table></div>')


def render_report(aggregate: Mapping[str, Any]) -> str:
    if "experiments" not in aggregate:
        aggregate = aggregate_experiments([dict(aggregate)])
    sections = []
    status_labels = {"not_run": "Not run", "planned": "Planned", "running": "In progress",
                     "complete": "Replay complete", "incomplete": "Coverage incomplete", "failed_closed": "Stopped"}
    for lane in aggregate["lanes"]:
        decisions = [[GATE_LABELS.get(gate, str(gate).replace("_", " ").capitalize()),
                      CHOICES.get(gate, {}).get(choice, str(choice).replace("_", " ").capitalize()), count]
                     for gate, counts in lane["choices"].items() for choice, count in counts.items()]
        coverage = [["Incomplete checks or abstentions", lane["incomplete_checks"]],
            ["Tool decisions with all pin IDs represented", lane["pin_coverage_complete"]],
            ["Tool decisions with incomplete pin IDs", lane["pin_coverage_incomplete"]],
            ["Hard-deny bypasses of pin judgment", lane["pin_coverage_bypassed"]],
            ["Auto-mode deterministic policy bypasses", lane["policy_bypasses"]],
            ["Omitted evidence references", lane["omitted_evidence_refs"]],
            ["Native compaction boundaries with unknown semantic retention", lane["compaction_semantics_unknown"]],
            ["Unsupported gate rows", lane["unsupported_rows"]], ["Unknown status rows", lane["unknown_status_rows"]],
            ["Unrecognized decision labels omitted", lane["unknown_choice_rows"]],
            ["Rows lacking logical event identity", lane["identity_unavailable_rows"]],
            ["Probability rows excluded", lane["invalid_probability_rows"]]]
        attempts = [["Receipt lines observed", lane["attempt_rows"]], ["Current logical checks", lane["rows"]],
            ["Retry rows superseded", lane["retry_rows"]], ["Exact duplicate rows excluded", lane["exact_duplicate_rows"]],
            ["Explicit uncached model attempts", lane["model_attempts"] if lane["attempt_metadata_rows"] else "Unavailable"],
            ["Explicit cache attempts", lane["cache_attempts"] if lane["attempt_metadata_rows"] else "Unavailable"]]
        timing = f'{lane["timed_checks"]:,} current uncached timed checks; median {lane["latency_p50_ms"] if lane["latency_p50_ms"] is not None else "unavailable"} ms; 95th percentile {lane["latency_p95_ms"] if lane["latency_p95_ms"] is not None else "unavailable"} ms; {lane["cached_timed_checks"]:,} cached timings excluded.'
        sections.append(f'<section class="card"><h2>{ADAPTERS[lane["adapter"]]} · {html.escape(lane["label"])}</h2>'
            f'<p>{status_labels[lane["status"]]} · Experiment {lane["experiment_fingerprint"]} · {lane["fingerprint_kind"]} {lane["fingerprint"]}</p>'
            f'<p class="muted">{LIMITS[lane["adapter"]]}</p>'
            + _table(["Recorded check", "Current count"], [[GATE_LABELS.get(gate, str(gate).replace("_", " ").capitalize()), count] for gate, count in lane["gates"].items()])
            + '<h3>Decision counts</h3>' + (_table(["Gate", "Output", "Count"], decisions) if decisions else '<p>No decisions recorded.</p>')
            + '<h3>Attempts and cache activity</h3>' + _table(["Observation", "Count"], attempts)
            + ('<h3>Supplied summary counters</h3>' + _table(["Counter", "Count"], [[name.replace("_", " "), value] for name, value in lane["execution"].items()]) if lane["execution"] else '')
            + '<h3>Coverage and omissions</h3>' + _table(["Observation", "Count"], coverage)
            + '<h3>Reported option scores</h3>' + _table(["Score band", _score_meta(lane)[0]], [[label, lane["answer_probability_bins"].get(label, 0)] for label in PROBABILITY_BINS])
            + f'<p class="muted">{_score_meta(lane)[1]}</p>'
            + f'<p class="muted">{timing}</p></section>')
    if aggregate["compaction"]["attempt_rows"]:
        compact = aggregate["compaction"]
        sections.append('<section class="card"><h2>Compaction receipt accounting</h2>'
            + _table(["Observation", "Count"], [["Aggregate files supplied", compact["attempt_rows"]],
                ["Current aggregates", len(compact["receipts"])], ["Exact duplicates excluded", compact["exact_duplicate_rows"]],
                ["Unsupported aggregate receipts omitted", compact["unsupported_rows"]]]) + '</section>')
    for receipt in aggregate["compaction"]["receipts"]:
        rows = [[COMPACTION_STATS[name], value] for name, value in receipt["stats"].items()]
        rows += [["OpenJev requests", receipt["requests"]], ["Validated responses", receipt["validated_responses"]],
                 ["User/assistant text unchanged", {True: "Yes", False: "No", None: "Unknown"}[receipt["text_unchanged"]]],
                 ["Context fitting reported", "Yes" if receipt["state_fitting_reported"] else "No / unavailable"],
                 ["Reduction ratio", receipt["reduction_ratio"]], ["Median request milliseconds", receipt["latency_p50_ms"]],
                 ["95th percentile milliseconds", receipt["latency_p95_ms"]]]
        rows += [[{"keep": "Keep", "drop_result": "Drop result", "drop_call": "Drop call"}[name], value] for name, value in receipt["actions"].items()]
        sections.append(f'<section class="card"><h2>{ADAPTERS["compaction"]} · {receipt["label"]}</h2>'
            f'<p>{status_labels[receipt["status"]]} · Receipt fingerprint {receipt["fingerprint"]}</p>'
            f'<p class="muted">{LIMITS["compaction"]}</p>' + _table(["Aggregate observation", "Value"], rows)
            + '<p class="muted">A missing frozen configuration identity prevents reliable retry deduplication across differing aggregate receipts. Exact duplicates are excluded. A/B candidate scores are uncalibrated.</p></section>')
    validation = []
    for key, label in (("holdout", "Hidden whole-session holdout"), ("metamorphic", "M01–M14 metamorphic suite")):
        value = aggregate["validation"][key]
        state = value["status"].replace("_", " ").capitalize()
        if value.get("evidence_supplied"):
            state += " (supplied evidence metadata)"
        validation.append([label, state])
    source_rows = [[row["label"], row["status"].capitalize(), row.get("observed_events", "Unverified"), row.get("expected_events", "Unverified")]
                   for row in aggregate["sources"]]
    partition_section = ''
    partition = aggregate.get("exploratory_partition")
    if partition is not None:
        rows = [[PARTITION_COUNTS[name], partition[name]] for name in PARTITION_COUNTS if name in partition]
        rows += [["Partition manifest SHA-256", partition["partition_manifest_sha256"]]]
        if "source_manifest_sha256" in partition:
            rows.append(["Source manifest SHA-256", partition["source_manifest_sha256"]])
        partition_section = ('<section class="card"><h2>Exploratory partition</h2>'
            f'<p>{EXPLORATORY_TIMING}</p><p>Use for exploratory analysis only. This partition supplies no evidence of a hidden or preregistered evaluation. Hidden whole-session holdout: Not implemented.</p>'
            + _table(["Supplied aggregate metadata", "Value"], rows) + '</section>')
    empty = '<section class="card"><h2>No replay receipts yet</h2><p>Not run. This page contains no model decisions or benchmark scores.</p></section>' if not sections else ''
    return f'''<!doctype html>
<html lang="en" data-bs-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>Blind local replay</title>
<style>:root{{color-scheme:dark;font-family:system-ui,sans-serif;background:#0b0f14;color:#e6edf3}}body{{margin:0}}main{{max-width:1100px;margin:auto;padding:32px 20px}}h1{{font-size:2rem}}h2{{font-size:1.4rem}}h3{{font-size:1rem;margin-top:24px}}p{{line-height:1.6}}.muted{{color:#9caec1}}.card{{background:#141c26;border:1px solid #2a3747;border-radius:10px;padding:24px;margin:20px 0}}.stats{{display:flex;gap:16px;flex-wrap:wrap}}.stat{{background:#141c26;border:1px solid #2a3747;padding:18px 22px;border-radius:10px;flex:1;min-width:140px}}.value{{display:block;font-size:1.5rem;font-weight:650}}.table-wrap{{overflow:auto}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid #2a3747}}th{{color:#9caec1}}footer{{padding:20px 0;color:#9caec1}}</style></head>
<body><main><p class="muted">Local replay · aggregate observations</p><h1>Blind local replay</h1>
<p>Baseline walk-forward decisions, auto-mode tool decisions, and upstream compaction are separate experiments. Correctness and recovered task outcomes remain unmeasured.</p>
<div class="stats"><div class="stat"><span class="value">{aggregate["receipt_rows"]:,}</span>Current checks and aggregate receipts</div><div class="stat"><span class="value">{aggregate["attempt_rows"]:,}</span>Receipt lines and aggregate inputs</div><div class="stat"><span class="value">{aggregate["unsupported_rows"]:,}</span>Unsupported adapter rows omitted</div></div>
<section class="card"><h2>Validation and remaining coverage</h2>{_table(["Validation", "Status"], validation)}
<p class="muted">Supplied evidence metadata is shown as supplied; the renderer does not run validation. Existing reviewed runs cannot acquire hidden-holdout status retroactively.</p>
{_table(["Requested baseline model", "Availability"], [[row["label"], row["status"]] for row in aggregate["roster"]])}
{_table(["Source", "Status", "Observed events", "Expected events"], source_rows)}</section>
<section class="card"><h2>How to read this page</h2><p>Current decision counts use the latest receipt for each stable event/gate/chunk identity. Earlier retries and identical rows are counted separately. Rows without event identity can only be deduplicated exactly.</p><p>Research excerpts are supporting checks, not combined routing decisions. Pin ID coverage does not verify full character-span coverage. Timing is unavailable when receipts omit it. Native compaction metadata and tool-pruning ratios do not establish semantic retention.</p></section>
{partition_section}{empty}{''.join(sections)}<footer>Aggregate counts only. Message content, event identifiers, tool arguments, prompts, reference answers, diagnostic reasons, endpoint addresses, and arbitrary metadata are omitted.</footer></main></body></html>'''


def _md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not headers or not rows:
        return ""
    str_headers = [str(h) for h in headers]
    str_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(h) for h in str_headers]
    for row in str_rows:
        for idx, cell in enumerate(row):
            if idx < len(widths):
                widths[idx] = max(widths[idx], len(cell))
            else:
                widths.append(len(cell))
    header_line = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(str_headers)) + " |"
    sep_line = "| " + " | ".join("-" * max(widths[i], 3) for i in range(len(str_headers))) + " |"
    row_lines = [
        "| " + " | ".join(row[i].ljust(widths[i]) if i < len(row) else "".ljust(widths[i]) for i in range(len(str_headers))) + " |"
        for row in str_rows
    ]
    return "\n".join([header_line, sep_line] + row_lines)


def render_markdown(aggregate: Mapping[str, Any]) -> str:
    if "experiments" not in aggregate:
        aggregate = aggregate_experiments([dict(aggregate)])
    status_labels = {
        "not_run": "Not run", "planned": "Planned", "running": "In progress",
        "complete": "Replay complete", "incomplete": "Coverage incomplete", "failed_closed": "Stopped"
    }

    lines = [
        "# Blind local replay",
        "",
        "_Local replay · aggregate observations_",
        "",
        "Baseline walk-forward decisions, auto-mode tool decisions, and upstream compaction are separate experiments. Correctness and recovered task outcomes remain unmeasured.",
        "",
        "## Overview",
        "",
        _md_table(
            ["Observation", "Count"],
            [
                ["Current checks and aggregate receipts", f'{aggregate["receipt_rows"]:,}'],
                ["Receipt lines and aggregate inputs", f'{aggregate["attempt_rows"]:,}'],
                ["Unsupported adapter rows omitted", f'{aggregate["unsupported_rows"]:,}'],
            ]
        ),
        "",
        "## Validation and remaining coverage",
        "",
    ]

    validation = []
    for key, label in (("holdout", "Hidden whole-session holdout"), ("metamorphic", "M01–M14 metamorphic suite")):
        val = aggregate["validation"][key]
        state = val["status"].replace("_", " ").capitalize()
        if val.get("evidence_supplied"):
            state += " (supplied evidence metadata)"
        validation.append([label, state])
    lines.append(_md_table(["Validation", "Status"], validation))
    lines.extend([
        "",
        "_Supplied evidence metadata is shown as supplied; the renderer does not run validation. Existing reviewed runs cannot acquire hidden-holdout status retroactively._",
        "",
        _md_table(["Requested baseline model", "Availability"], [[row["label"], row["status"]] for row in aggregate["roster"]]),
        "",
        _md_table(
            ["Source", "Status", "Observed events", "Expected events"],
            [[row["label"], row["status"].capitalize(), row.get("observed_events", "Unverified"), row.get("expected_events", "Unverified")]
             for row in aggregate["sources"]]
        ),
        "",
        "## Scope and interpretation limits",
        "",
        "Current decision counts use the latest receipt for each stable event/gate/chunk identity. Earlier retries and identical rows are counted separately. Rows without event identity can only be deduplicated exactly.",
        "",
        "Research excerpts are supporting checks, not combined routing decisions. Pin ID coverage does not verify full character-span coverage. Timing is unavailable when receipts omit it. Native compaction metadata and tool-pruning ratios do not establish semantic retention.",
        "",
    ])

    partition = aggregate.get("exploratory_partition")
    if partition is not None:
        part_rows = [[PARTITION_COUNTS[name], partition[name]] for name in PARTITION_COUNTS if name in partition]
        part_rows.append(["Partition manifest SHA-256", partition["partition_manifest_sha256"]])
        if "source_manifest_sha256" in partition:
            part_rows.append(["Source manifest SHA-256", partition["source_manifest_sha256"]])
        lines.extend([
            "## Exploratory partition",
            "",
            EXPLORATORY_TIMING,
            "",
            "Use for exploratory analysis only. This partition supplies no evidence of a hidden or preregistered evaluation. Hidden whole-session holdout: Not implemented.",
            "",
            _md_table(["Supplied aggregate metadata", "Value"], part_rows),
            "",
        ])

    has_content = bool(aggregate["lanes"] or aggregate["compaction"]["receipts"] or aggregate["compaction"]["attempt_rows"])
    if not has_content:
        lines.extend([
            "## No replay receipts yet",
            "",
            "Not run. This report contains no model decisions or benchmark scores.",
            "",
        ])

    for lane in aggregate["lanes"]:
        lines.extend([
            f'## {ADAPTERS[lane["adapter"]]} · {lane["label"]}',
            "",
            f'- **Status**: {status_labels[lane["status"]]}',
            f'- **Experiment**: {lane["experiment_fingerprint"]}',
            f'- **{lane["fingerprint_kind"].capitalize()}**: {lane["fingerprint"]}',
            f'- **Explicit limits**: {LIMITS[lane["adapter"]]}',
            "",
            "### Recorded checks",
            "",
        ])
        gate_rows = [[GATE_LABELS.get(gate, str(gate).replace("_", " ").capitalize()), count] for gate, count in lane["gates"].items()]
        lines.append(_md_table(["Recorded check", "Current count"], gate_rows) if gate_rows else "No recorded checks.")
        lines.extend([
            "",
            "### Route totals",
            "",
        ])
        route_rows = []
        for gate, counts in lane["choices"].items():
            if "route" in gate:
                for choice, count in counts.items():
                    choice_label = CHOICES.get(gate, {}).get(choice, str(choice).replace("_", " ").capitalize())
                    route_rows.append([GATE_LABELS.get(gate, gate.replace("_", " ").capitalize()), choice_label, count])
            else:
                for choice, count in counts.items():
                    if choice in {"go", "loop", "hold", "reconfirm_intent", "rethink_plan", "research_more", "dispatch_verifier", "escalate", "proceed"}:
                        choice_label = CHOICES.get(gate, {}).get(choice, str(choice).replace("_", " ").capitalize())
                        route_rows.append([GATE_LABELS.get(gate, gate.replace("_", " ").capitalize()), choice_label, count])
        lines.append(_md_table(["Gate", "Route", "Count"], route_rows) if route_rows else "No route decisions recorded.")
        lines.extend([
            "",
            "### Decision counts",
            "",
        ])
        decisions = [
            [GATE_LABELS[gate], CHOICES[gate][choice], count]
            for gate, counts in lane["choices"].items() if gate in CHOICES
            for choice, count in counts.items() if choice in CHOICES[gate]
        ]
        lines.append(_md_table(["Gate", "Output", "Count"], decisions) if decisions else "No decisions recorded.")
        lines.extend([
            "",
            "### Attempts and cache activity",
            "",
            _md_table(
                ["Observation", "Count"],
                [
                    ["Receipt lines observed", lane["attempt_rows"]],
                    ["Current logical checks", lane["rows"]],
                    ["Retry rows superseded", lane["retry_rows"]],
                    ["Exact duplicate rows excluded", lane["exact_duplicate_rows"]],
                    ["Explicit uncached model attempts", lane["model_attempts"] if lane["attempt_metadata_rows"] else "Unavailable"],
                    ["Explicit cache attempts", lane["cache_attempts"] if lane["attempt_metadata_rows"] else "Unavailable"],
                ]
            ),
            "",
        ])

        if lane["execution"]:
            lines.extend([
                "### Supplied summary counters",
                "",
                _md_table(["Counter", "Count"], [[name.replace("_", " "), value] for name, value in lane["execution"].items()]),
                "",
            ])

        coverage = [
            ["Incomplete checks or abstentions", lane["incomplete_checks"]],
            ["Tool decisions with all pin IDs represented", lane["pin_coverage_complete"]],
            ["Tool decisions with incomplete pin IDs", lane["pin_coverage_incomplete"]],
            ["Hard-deny bypasses of pin judgment", lane["pin_coverage_bypassed"]],
            ["Auto-mode deterministic policy bypasses", lane["policy_bypasses"]],
            ["Omitted evidence references", lane["omitted_evidence_refs"]],
            ["Native compaction boundaries with unknown semantic retention", lane["compaction_semantics_unknown"]],
            ["Unsupported gate rows", lane["unsupported_rows"]],
            ["Unknown status rows", lane["unknown_status_rows"]],
            ["Unrecognized decision labels omitted", lane["unknown_choice_rows"]],
            ["Rows lacking logical event identity", lane["identity_unavailable_rows"]],
            ["Probability rows excluded", lane["invalid_probability_rows"]],
        ]
        lines.extend([
            "### Coverage and omissions",
            "",
            _md_table(["Observation", "Count"], coverage),
            "",
            "### Reported option scores",
            "",
            _md_table(["Score band", _score_meta(lane)[0]], [[label, lane["answer_probability_bins"].get(label, 0)] for label in PROBABILITY_BINS]),
            "",
            f"_{_score_meta(lane)[1]}_",
            "",
            "### Latency and timing",
            "",
            f'- **Timed checks**: {lane["timed_checks"]:,} current uncached timed checks',
            f'- **Median latency (p50)**: {lane["latency_p50_ms"] if lane["latency_p50_ms"] is not None else "unavailable"} ms',
            f'- **95th percentile latency (p95)**: {lane["latency_p95_ms"] if lane["latency_p95_ms"] is not None else "unavailable"} ms',
            f'- **Cached timings excluded**: {lane["cached_timed_checks"]:,}',
            "",
        ])

    if aggregate["compaction"]["attempt_rows"]:
        compact = aggregate["compaction"]
        lines.extend([
            "## Compaction receipt accounting",
            "",
            _md_table(
                ["Observation", "Count"],
                [
                    ["Aggregate files supplied", compact["attempt_rows"]],
                    ["Current aggregates", len(compact["receipts"])],
                    ["Exact duplicates excluded", compact["exact_duplicate_rows"]],
                    ["Unsupported aggregate receipts omitted", compact["unsupported_rows"]],
                ]
            ),
            "",
        ])

    for receipt in aggregate["compaction"]["receipts"]:
        c_rows = [[COMPACTION_STATS[name], value] for name, value in receipt["stats"].items()]
        c_rows += [
            ["OpenJev requests", receipt["requests"]],
            ["Validated responses", receipt["validated_responses"]],
            ["User/assistant text unchanged", {True: "Yes", False: "No", None: "Unknown"}[receipt["text_unchanged"]]],
            ["Context fitting reported", "Yes" if receipt["state_fitting_reported"] else "No / unavailable"],
            ["Reduction ratio", receipt["reduction_ratio"]],
            ["Median request milliseconds", receipt["latency_p50_ms"]],
            ["95th percentile milliseconds", receipt["latency_p95_ms"]],
        ]
        c_rows += [
            [{"keep": "Keep", "drop_result": "Drop result", "drop_call": "Drop call"}[name], value]
            for name, value in receipt["actions"].items()
        ]
        lines.extend([
            f'## {ADAPTERS["compaction"]} · {receipt["label"]}',
            "",
            f'- **Status**: {status_labels[receipt["status"]]}',
            f'- **Receipt fingerprint**: {receipt["fingerprint"]}',
            f'- **Explicit limits**: {LIMITS["compaction"]}',
            "",
            _md_table(["Aggregate observation", "Value"], c_rows),
            "",
            "_A missing frozen configuration identity prevents reliable retry deduplication across differing aggregate receipts. Exact duplicates are excluded. A/B candidate scores are uncalibrated._",
            "",
        ])

    lines.extend([
        "---",
        "",
        "Aggregate counts only. Message content, event identifiers, tool arguments, prompts, reference answers, diagnostic reasons, endpoint addresses, and arbitrary metadata are omitted.",
        "",
    ])
    return "\n".join(lines)


def write_markdown_report(aggregate: Mapping[str, Any], path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_markdown(aggregate), encoding="utf-8", newline="\n")
    return target


def _experiment_from_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    run_id = summary.get("run_id")
    requested_id = _identifier(run_id) if run_id is not None else "summary-run"
    adapter_id = str(summary.get("adapter_id", summary.get("adapter", "baseline")))
    adapter = _summary_adapter(summary)
    model_val = summary.get("model") or summary.get("model_id") or summary.get("lane_id") or "laya"
    model_key = _model_key(model_val, summary.get("lane_id"))
    label = MODEL_LABELS.get(model_key, "Laya")
    lane_id = str(summary.get("lane_id") or summary.get("adapter_id") or model_key)
    status = summary.get("status")
    if status not in RUN_STATUSES:
        status = "complete" if status in {"completed", "scored", "success"} else "running" if status else "not_run"
    if status == "completed_with_incomplete_jobs":
        status = "incomplete"

    execution = {name: value for name in ("inference_requests", "decision_calls", "cache_hits", "incomplete_count", "model_calls")
                 if (value := _count(summary.get(name))) is not None}

    planned = _count(summary.get("planned_jobs")) or _count(summary.get("decision_calls")) or 0
    scored = _count(summary.get("scored_jobs")) or _count(summary.get("inference_requests")) or 0
    incomplete = _count(summary.get("incomplete_jobs")) or _count(summary.get("incomplete_count")) or 0

    latency_p50 = _finite(summary.get("latency_p50_ms"))
    latency_p95 = _finite(summary.get("latency_p95_ms"))
    if latency_p50 is None and _finite(summary.get("elapsed_seconds")) and scored > 0:
        latency_p50 = round((float(summary["elapsed_seconds"]) / scored) * 1000, 2)

    choices: dict[str, Counter] = {}
    phase2 = summary.get("phase2")
    if isinstance(phase2, dict):
        routes = phase2.get("routes") or phase2.get("route_totals")
        if isinstance(routes, dict):
            for route_name, count in routes.items():
                if isinstance(count, int):
                    choices.setdefault("laya_route", Counter())[str(route_name)] = count
    prob_bins = Counter({"Below 0.50": 0, "0.50 to below 0.75": 0, "0.75 to below 0.90": 0, "0.90 to 1.00": 0})
    skipped_rows = 0
    source_path = summary.get("_source_path")
    if source_path:
        parent_dir = Path(source_path).parent
        agg_path = parent_dir / "aggregates.jsonl"
        if agg_path.exists():
            route_pairs: set[tuple[str, str]] = set()
            for line in agg_path.open(encoding="utf-8"):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    rt = row.get("recommended_route")
                    rid = str(row.get("record_type") or "")
                    eid = row.get("event_id")
                    if rt and eid and not rid.endswith("_plan"):
                        route_pairs.add((str(eid), str(rt)))
                except json.JSONDecodeError:
                    skipped_rows += 1
            for _eid, rt in route_pairs:
                choices.setdefault("laya_route", Counter())[rt] += 1
        jobs_path = parent_dir / "jobs.jsonl"
        if jobs_path.exists():
            for line in jobs_path.open(encoding="utf-8"):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    ans = row.get("answers") or {}
                    for q, a in ans.items():
                        if isinstance(a, dict):
                            c = a.get("choice")
                            if c:
                                choices.setdefault(q, Counter())[str(c)] += 1
                            p = a.get("answer_confidence")
                            if isinstance(p, (int, float)):
                                if p < 0.5: prob_bins["Below 0.50"] += 1
                                elif p < 0.75: prob_bins["0.50 to below 0.75"] += 1
                                elif p < 0.9: prob_bins["0.75 to below 0.90"] += 1
                                else: prob_bins["0.90 to 1.00"] += 1
                except json.JSONDecodeError:
                    skipped_rows += 1
    if isinstance(summary.get("choices"), dict):
        for g, c in summary["choices"].items():
            if isinstance(c, dict):
                choices.setdefault(g, Counter()).update({k: v for k, v in c.items() if isinstance(v, int)})

    gates: dict[str, int] = {}
    if isinstance(summary.get("gates"), dict):
        gates = {str(k): v for k, v in summary["gates"].items() if isinstance(v, int)}
    elif isinstance(summary.get("phase1"), dict) or isinstance(phase2, dict):
        for bucket in (summary.get("phase1"), phase2):
            if not isinstance(bucket, dict):
                continue
            for k, v in bucket.items():
                if isinstance(v, int):
                    gates[str(k)] = v
    for g, c in choices.items():
        gates.setdefault(g, sum(c.values()))

    total_rows = scored or planned or sum(gates.values())
    lane = {
        "adapter": adapter,
        "label": label,
        "model_key": model_key,
        "lane_id": lane_id,
        "status": status,
        "experiment_fingerprint": _digest(requested_id)[:12],
        "fingerprint_kind": "profile",
        "fingerprint": str(summary.get("profile_sha256") or summary.get("receipt_sha256") or _digest(summary)),
        "gates": gates,
        "choices": choices,
        "incomplete_checks": incomplete,
        "pin_coverage_complete": _count(summary.get("pin_coverage_complete")) or 0,
        "pin_coverage_incomplete": _count(summary.get("pin_coverage_incomplete")) or 0,
        "pin_coverage_bypassed": _count(summary.get("pin_coverage_bypassed")) or 0,
        "policy_bypasses": _count(summary.get("policy_bypasses")) or 0,
        "omitted_evidence_refs": _count(summary.get("omitted_evidence_refs")) or 0,
        "compaction_semantics_unknown": _count(summary.get("compaction_semantics_unknown")) or 0,
        "unsupported_rows": skipped_rows,
        "unknown_status_rows": 0,
        "unknown_choice_rows": 0,
        "identity_unavailable_rows": 0,
        "invalid_probability_rows": _count(summary.get("invalid_probability_rows")) or 0,
        "attempt_rows": planned or total_rows,
        "rows": total_rows,
        "retry_rows": _count(summary.get("retry_rows")) or 0,
        "exact_duplicate_rows": _count(summary.get("exact_duplicate_rows")) or 0,
        "model_attempts": scored or total_rows,
        "cache_attempts": _count(summary.get("cache_hits")) or 0,
        "attempt_metadata_rows": total_rows,
        "timed_checks": total_rows,
        "cached_timed_checks": 0,
        "latency_p50_ms": latency_p50,
        "latency_p95_ms": latency_p95,
        "execution": execution,
        "answer_probability_bins": prob_bins,
    }
    return {
        "schema_version": 2,
        "status": status,
        "run_id": requested_id,
        "content_included": False,
        "lane_count": 1,
        "unsupported_rows": 0,
        "receipt_rows": total_rows,
        "attempt_rows": planned or total_rows,
        "lanes": [lane],
    }


def _read_content_free(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("content_free_summary_required")
    if value.get("content_included") is True:
        raise ValueError("content_free_summary_required")
    if value.get("content_included") is None:
        forbidden = {"prompt", "content", "prose", "messages", "transcript", "raw_answers"}
        if any(k in value for k in forbidden):
            raise ValueError("content_free_summary_required")
    value["_source_path"] = str(path)
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render aggregate receipts; never reads transcript sources or calls models.")
    parser.add_argument("--receipt-dir", type=Path, action="append", default=[], help="Repeat for separate private run directories.")
    parser.add_argument("--run-id", help="Expected run ID, for one receipt directory only.")
    parser.add_argument("--summary", type=Path, action="append", default=[], help="Repeat content-free summaries; match by run ID or directory order.")
    parser.add_argument("--compaction-receipt", type=Path, action="append", default=[], help="Repeat private aggregate compaction JSON files.")
    parser.add_argument("--report-context", type=Path, help="Content-free source/roster/validation evidence metadata.")
    parser.add_argument("--out", type=Path, default=None, help="Output file path (default: blind-local-replay.html for HTML, laya-benchmark.md for Markdown).")
    parser.add_argument("--format", choices=["html", "markdown", "md"], default=None, help="Output format (html or markdown; inferred from --out suffix if omitted).")
    parser.add_argument("--markdown", action="store_true", help="Render markdown report instead of HTML.")
    parser.add_argument("--aggregate", type=Path, help="Pre-computed content-free aggregate JSON file.")

    format_override = None
    args_list = list(argv) if argv is not None else sys.argv[1:]
    if args_list and args_list[0] in {"markdown", "md", "render-markdown"}:
        format_override = "markdown"
        args_list = args_list[1:]

    args = parser.parse_args(args_list)
    try:
        is_markdown = (
            format_override == "markdown"
            or args.markdown
            or (args.format in {"markdown", "md"})
            or (args.out is not None and args.out.suffix.lower() in {".md", ".markdown"})
        )
        out_path = args.out or (DEFAULT_MD_REPORT if is_markdown else DEFAULT_REPORT)

        if args.run_id and len(args.receipt_dir) != 1:
            raise ValueError("run_id_requires_one_run_directory")

        summaries = [_read_content_free(path) for path in args.summary]
        experiments = []

        if args.aggregate:
            agg_data = _read_content_free(args.aggregate)
            if "experiments" in agg_data:
                aggregate = agg_data
            elif "lanes" in agg_data:
                experiments.append(agg_data)
            else:
                experiments.append(_experiment_from_summary(agg_data))

        for index, directory in enumerate(args.receipt_dir):
            paths = sorted(directory.glob("*/events.jsonl"))
            if (directory / "events.jsonl").exists():
                paths.append(directory / "events.jsonl")
            if not paths:
                raise ValueError("receipt_files_not_found")
            experiment = aggregate_receipts(paths, run_id=args.run_id)
            matches = [summary for summary in summaries if summary.get("run_id") == experiment["run_id"]]
            summary = matches[0] if len(matches) == 1 else summaries[index] if len(summaries) == len(args.receipt_dir) else None
            if summary and summary.get("run_id") not in {None, experiment["run_id"]}:
                raise ValueError("summary_run_mismatch")
            if summary:
                experiment = aggregate_receipts(paths, run_id=args.run_id, run_summary=summary)
            experiments.append(experiment)

        if not args.receipt_dir and summaries and not args.aggregate:
            for summary in summaries:
                if "lanes" in summary:
                    experiments.append(summary)
                elif "experiments" in summary:
                    aggregate = summary
                    break
                else:
                    experiments.append(_experiment_from_summary(summary))

        if 'aggregate' not in locals():
            context = _read_content_free(args.report_context) if args.report_context else None
            aggregate = aggregate_experiments(experiments, aggregate_compaction(args.compaction_receipt), context)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        content = render_markdown(aggregate) if is_markdown else render_report(aggregate)
        out_path.write_text(content, encoding="utf-8", newline="\n")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        print(json.dumps({"status": "rejected", "reason": "report_input_invalid", "inference_called": False}))
        return 2
    print(json.dumps({"status": "rendered", "receipt_rows": aggregate["receipt_rows"],
                      "attempt_rows": aggregate["attempt_rows"], "content_included": False, "inference_called": False}, sort_keys=True))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
