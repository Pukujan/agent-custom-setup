#!/usr/bin/env python3
"""Derive content-free research outcome/route rows from v1 receipt chunks.

This is an offline receipt aggregator. It never reads model prompts or calls a
decision backend, and it writes a separate derived JSONL file without changing
any source receipt.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


VALID_CHOICE = {"ready", "research_more", "insufficient"}
VALID_STATUS = {"scored_chunk", "scored_empty", "incomplete", "scored"}
AGGREGATE_SCHEMA_VERSION = 1


class AggregateError(ValueError):
    """Invalid source receipt identity or output path."""


GroupKey = Tuple[str, str, str, str, str]


def _required_string(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AggregateError(f"missing_{key}")
    return value


def _group_key(row: Mapping[str, Any]) -> GroupKey:
    if row.get("schema_version") != 1:
        raise AggregateError("source_schema_not_v1")
    return (
        _required_string(row, "run_id"),
        _required_string(row, "lane_id"),
        _required_string(row, "model_id"),
        _required_string(row, "stream_id_sha256"),
        _required_string(row, "event_id"),
    )


def _read_source_rows(paths: Sequence[Path]) -> Dict[GroupKey, List[Dict[str, Any]]]:
    groups: Dict[GroupKey, List[Dict[str, Any]]] = defaultdict(list)
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as source:
                for line_number, line in enumerate(source, 1):
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise AggregateError("source_jsonl_invalid") from exc
                    if not isinstance(row, dict):
                        raise AggregateError("source_row_not_object")
                    if row.get("gate") != "research":
                        continue
                    key = _group_key(row)
                    groups[key].append({
                        # Copy only fields needed for aggregation. Arbitrary
                        # payload fields such as text/prompt are discarded.
                        "status": row.get("status"),
                        "choice": row.get("choice"),
                        "evidence_ids": row.get("evidence_ids", []),
                        "included_evidence_ids": row.get("included_evidence_ids", []),
                        "omitted_evidence_ids": row.get("omitted_evidence_ids", []),
                        "inherited_evidence_ids": row.get("inherited_evidence_ids", []),
                        "claim_chunk_index": row.get("claim_chunk_index"),
                        "source_content_sha256": row.get("source_content_sha256"),
                        "event_kind": row.get("event_kind"),
                    })
        except OSError as exc:
            raise AggregateError("source_receipt_unreadable") from exc
    for rows in groups.values():
        rows.sort(key=lambda row: (
            str(row.get("claim_chunk_index")), str(row.get("status")),
            str(row.get("choice")),
        ))
    return groups


def _string_values(rows: Iterable[Mapping[str, Any]], field: str) -> List[str]:
    values = set()
    for row in rows:
        raw = row.get(field)
        if isinstance(raw, list):
            values.update(value for value in raw if isinstance(value, str) and value)
    return sorted(values)


def aggregate_group(key: GroupKey, rows: Sequence[Mapping[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
    run_id, lane_id, model_id, stream_hash, event_id = key
    statuses = [row.get("status") for row in rows]
    scored_rows = [row for row in rows if row.get("status") in VALID_STATUS - {"incomplete"}]
    incomplete_rows = [row for row in rows if row.get("status") == "incomplete"]
    invalid_rows = [row for row in rows if row.get("status") not in VALID_STATUS]
    choices = [row.get("choice") for row in scored_rows]
    invalid_choices = [value for value in choices if value not in VALID_CHOICE]
    valid_choices = [value for value in choices if value in VALID_CHOICE]
    source_hashes = sorted({row["source_content_sha256"] for row in rows
                            if isinstance(row.get("source_content_sha256"), str) and row["source_content_sha256"]})
    identity_conflict = len(source_hashes) > 1

    # Coverage is evaluated only from explicit receipt evidence. A missing
    # expected-chunk count in a v1 file is reported as unverified, never guessed.
    if incomplete_rows or invalid_rows or invalid_choices or identity_conflict or not valid_choices:
        outcome = "incomplete"
        coverage_status = "explicitly_incomplete" if incomplete_rows or invalid_rows or invalid_choices or identity_conflict else "no_decisions_observed"
    elif any(choice == "insufficient" for choice in valid_choices):
        outcome = "insufficient"
        coverage_status = "no_incomplete_row_observed_unverified"
    elif any(choice == "research_more" for choice in valid_choices):
        outcome = "research_more"
        coverage_status = "no_incomplete_row_observed_unverified"
    elif valid_choices and all(choice == "ready" for choice in valid_choices):
        outcome = "ready"
        coverage_status = "no_incomplete_row_observed_unverified"
    else:
        outcome = "incomplete"
        coverage_status = "no_decisions_observed"

    route = {
        "ready": "go",
        "research_more": "loop",
        "insufficient": "hold",
        "incomplete": "hold",
    }[outcome]
    evidence_ids = sorted(set(
        _string_values(rows, "evidence_ids")
        + _string_values(rows, "included_evidence_ids")
        + _string_values(rows, "inherited_evidence_ids")
    ))
    omitted_ids = _string_values(rows, "omitted_evidence_ids")
    outcome_row: Dict[str, Any] = {
        "schema_version": AGGREGATE_SCHEMA_VERSION,
        "derived_from": "v1_research_chunk_receipts",
        "run_id": run_id, "lane_id": lane_id, "model_id": model_id,
        "stream_id_sha256": stream_hash, "event_id": event_id,
        "source_content_sha256": source_hashes[0] if len(source_hashes) == 1 else None,
        "gate": "research_outcome_aggregate",
        "research_outcome": outcome,
        "coverage_status": coverage_status,
        "source_receipt_rows": len(rows),
        "scored_chunk_rows": sum(row.get("status") == "scored_chunk" for row in rows),
        "scored_empty_rows": sum(row.get("status") == "scored_empty" for row in rows),
        "incomplete_rows": len(incomplete_rows),
        "invalid_rows": len(invalid_rows),
        "invalid_choice_rows": len(invalid_choices),
        "distinct_claim_chunk_indices": len({row.get("claim_chunk_index") for row in rows
                                              if isinstance(row.get("claim_chunk_index"), int)}),
        "distinct_evidence_ids": len(evidence_ids),
        "omitted_evidence_ids": omitted_ids,
        "evidence_ids": evidence_ids,
        "expected_chunk_count_available": False,
        "content_included": False,
    }
    route_row = None
    event_kinds = {row.get("event_kind") for row in rows}
    if "tool_call" in event_kinds:
        route_row = {
            "schema_version": AGGREGATE_SCHEMA_VERSION,
            "derived_from": "v1_research_chunk_receipts",
            "run_id": run_id, "lane_id": lane_id, "model_id": model_id,
            "stream_id_sha256": stream_hash, "event_id": event_id,
            "source_content_sha256": source_hashes[0] if len(source_hashes) == 1 else None,
            "gate": "research_route",
            "research_outcome": outcome, "route": route,
            "shadow_permission": {
                "go": "would_allow_coding",
                "loop": "would_hold_for_more_research",
                "hold": "would_hold_for_escalation_or_incomplete_evidence",
            }[route],
            "shadow_only": True, "enforcement_applied": False,
            "coverage_status": coverage_status,
            "source_receipt_rows": len(rows),
            "scored_chunk_rows": outcome_row["scored_chunk_rows"],
            "incomplete_rows": len(incomplete_rows),
            "evidence_ids": evidence_ids,
            "omitted_evidence_ids": omitted_ids,
            "expected_chunk_count_available": False,
            "content_included": False,
        }
    return outcome_row, route_row


def aggregate_receipts(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    groups = _read_source_rows(paths)
    result: List[Dict[str, Any]] = []
    for key in sorted(groups):
        outcome, route = aggregate_group(key, groups[key])
        result.append(outcome)
        if route is not None:
            result.append(route)
    return result


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def write_aggregate(paths: Sequence[Path], output: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    resolved_inputs = [path.resolve() for path in paths]
    output = output.expanduser().resolve()
    if output in resolved_inputs:
        raise AggregateError("output_must_not_be_source_receipt")
    if any(_is_within(output, input_path.parent) for input_path in resolved_inputs):
        raise AggregateError("output_must_be_outside_source_receipt_directories")
    if output.exists():
        raise AggregateError("output_already_exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise AggregateError("output_write_failed") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate existing v1 research receipts offline; no model calls.",
        epilog=("Example: python aggregate_research_receipts.py "
                "--input <lane-a-events.jsonl> --input <lane-b-events.jsonl> "
                "--output <derived/research-routes.jsonl>"),
    )
    parser.add_argument("--input", action="append", required=True, metavar="RECEIPTS.JSONL",
                        help="Source v1 receipt JSONL (repeat for multiple lane files).")
    parser.add_argument("--output", required=True, metavar="DERIVED.JSONL",
                        help="New derived outcome/route file outside source receipt directories.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        inputs = [Path(item).expanduser() for item in args.input]
        if any(not path.is_file() for path in inputs):
            raise AggregateError("source_receipt_missing")
        rows = aggregate_receipts(inputs)
        write_aggregate(inputs, Path(args.output), rows)
    except AggregateError as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc), "model_calls": 0}, sort_keys=True))
        return 2
    route_count = sum(row.get("gate") == "research_route" for row in rows)
    print(json.dumps({"status": "aggregated", "groups": sum(row.get("gate") == "research_outcome_aggregate" for row in rows),
                      "route_receipts": route_count, "rows_written": len(rows),
                      "model_calls": 0, "content_included": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
