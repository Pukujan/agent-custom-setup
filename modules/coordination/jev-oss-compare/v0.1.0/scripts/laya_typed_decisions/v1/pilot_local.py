"""Bounded LOCAL PILOT: run the frozen Laya v1 DAG on the capped harvest.

Owner direction 2026-09-29 (issue #28 comment 5897996850): run the benchmark
on this device while the verified 81-file corpus is unreachable. This entry
point drives the SAME frozen components as `runner.py run` (job builders,
worker pool, deterministic reducer, aggregate) over the checked-in capped
harvest export via harvest_adapter. The 81-file guard is not modified or
bypassed: `run`/`inspect` still refuse this input, and that refusal is the
point — this pilot is explicitly capped-harvest, non-blind, non-evidence.

Selection is by whole streams (chronological greedy under a job budget), so
route distributions measure model behavior, not a mid-stream cutoff.

Usage:
  python pilot_local.py --source <harvest.jsonl> --model-dir <snapshot> \
      --output <private-dir> --run-id <id> [--budget 1500] [--workers 2]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from laya_typed_decisions.v1 import runner
from laya_typed_decisions.v1.harvest_adapter import adapt


def _stream_events(events) -> Dict[str, List[Any]]:
    groups: Dict[str, List[Any]] = {}
    for event in events:
        groups.setdefault(event.stream_id, []).append(event)
    return {k: sorted(v, key=lambda e: e.sequence) for k, v in groups.items()}


def _tally(rows_: List[Dict[str, Any]], key: str, sub: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for row in rows_:
        bucket = f"{row.get(key)}|{row.get(sub)}"
        out[bucket] = out.get(bucket, 0) + 1
    return out


def _choices(rows_: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for row in rows_:
        answers = row.get("answers")
        if not isinstance(answers, dict):
            continue
        for qid, value in answers.items():
            if isinstance(value, dict):
                bucket = f"{qid}|{value.get('choice')}"
                out[bucket] = out.get(bucket, 0) + 1
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--budget", type=int, default=1500)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    profile = runner.load_profile()
    profile_hash = runner.profile_fingerprint(profile)
    model_path = Path(args.model_dir)
    runner._parse_remote_identity(model_path, profile)
    tokenizer = runner._load_tokenizer(model_path)
    workers, batch_size = runner._override_inference(profile, args.workers, None)

    rows = [json.loads(line) for line in
            args.source.read_text(encoding="utf-8").splitlines() if line.strip()]
    file_hash = runner._file_sha(args.source)
    events, adapt_stats = adapt(rows, file_hash=file_hash)
    groups = _stream_events(events)
    humans = {s: [e for e in rows_ if e.kind == "human_user" and e.authority == "human"]
              for s, rows_ in groups.items()}
    order = sorted(groups, key=lambda s: groups[s][0].sequence)

    selected: List[str] = []
    used = 0
    for stream_id in order:
        if not humans.get(stream_id):
            continue
        atoms = runner._event_atoms(
            groups[stream_id], tokenizer,
            int(profile["inference"]["state_chunk_tokens"]),
            int(profile["inference"]["state_chunk_overlap_tokens"]))
        phase1, _pairs = runner._phase1_jobs(
            args.run_id, profile_hash, profile, {stream_id: groups[stream_id]}, atoms)
        tools = sum(1 for e in groups[stream_id] if e.kind == "tool_call")
        estimate = len(phase1) + tools * len(humans[stream_id])
        if used + estimate > args.budget:
            continue
        selected.append(stream_id)
        used += estimate
    if not selected:
        print(json.dumps({"status": "failed", "reason": "no_stream_fits_budget"}))
        return 2

    streams = {s: groups[s] for s in selected}
    all_events = [e for s in selected for e in streams[s]]
    atoms_by_event = runner._event_atoms(
        all_events, tokenizer, int(profile["inference"]["state_chunk_tokens"]),
        int(profile["inference"]["state_chunk_overlap_tokens"]))
    phase1_jobs, expected_pairs = runner._phase1_jobs(
        args.run_id, profile_hash, profile, streams, atoms_by_event)

    args.output.mkdir(parents=True, exist_ok=True)
    receipts_path = args.output / "jobs.jsonl"
    existing = runner._existing_receipts(receipts_path)
    cache = runner._OutputCache(args.output / "cache" / f"{profile_hash[:24]}.sqlite")
    receipt_rows: List[Dict[str, Any]] = []

    def append_receipt(row: Dict[str, Any]) -> None:
        receipt_rows.append(row)
        runner._append_jsonl(receipts_path, row)

    started = time.monotonic()
    pool = runner._WorkerPool(model_path, profile, workers)
    try:
        pool.wait_ready()
        result_rows = dict(existing)
        phase1_results = pool.infer(phase1_jobs, profile, cache, result_rows,
                                    append_receipt, run_id=args.run_id,
                                    profile_hash=profile_hash)
        result_rows.update(phase1_results)
        phase2_jobs, deterministic_rows, reduction = runner._pin_state_and_phase2(
            args.run_id, profile_hash, profile, streams, atoms_by_event,
            phase1_jobs, phase1_results, tokenizer)
        phase2_results = pool.infer(phase2_jobs, profile, cache, result_rows,
                                    append_receipt, run_id=args.run_id,
                                    profile_hash=profile_hash)
        result_rows.update(phase2_results)
        final_rows = runner._aggregate_phase2(
            phase2_jobs, phase2_results, deterministic_rows,
            reduction["active_pins"],
            reduction["phase2"].get("stream_quality", {}))
    finally:
        pool.close()
    wall = round(time.monotonic() - started, 2)

    aggregates = [r for r in final_rows
                  if str(r.get("record_type", "")).endswith("_aggregate")]
    all_rows = list(result_rows.values())
    batch_ms = sorted(int(r.get("batch_elapsed_ms") or 0)
                      for r in all_rows if r.get("batch_elapsed_ms"))
    summary = {
        "record_type": "laya_pilot_receipt",
        "schema_version": 1,
        "label": ("capped-harvest LOCAL PILOT; non-blind; non-evidence; "
                  "NOT the 81-file benchmark replay"),
        "run_id": args.run_id,
        "identity": {
            "model_revision": profile["model"]["revision"],
            "sdk_version": profile["model"]["sdk_version"],
            "sdk_revision": profile["model"]["sdk_revision"],
            "profile_sha256": profile_hash,
            "source_file_sha256": file_hash,
            "workers": workers, "batch_size": batch_size,
        },
        "scope": {
            "harvest_rows": len(rows), "adapt_stats": adapt_stats,
            "streams_total": len(groups), "streams_included": len(selected),
            "streams_excluded": len(groups) - len(selected),
            "human_messages_included": sum(len(humans[s]) for s in selected),
            "budget": args.budget, "budget_estimate_used": used,
            "phase1_jobs": len(phase1_jobs), "phase2_jobs": len(phase2_jobs),
            "expected_message_pairs_included": expected_pairs,
        },
        "structural_limits": {
            "assistant_rows_in_export": 0,
            "exercised": ("pin status, message-pair relation, and the recorded "
                          "tool-action half of intent conflict (tool_pin_relation "
                          "verdicts/routes on real tool calls + human pins)"),
            "artifact_rows": ("acknowledgment omitted/reconfirm rows are EXPORT "
                              "ARTIFACTS: the harvest schema strips assistant "
                              "messages, so 'no next response' reflects export "
                              "truncation, not agent drift — never a catch-rate "
                              "signal"),
            "unexercised": ("assistant-prose plan boundaries/plan_intent and "
                            "research claim-evidence matching (issue #28 modes "
                            "2-prose/3/4): no assistant claim atoms exist in "
                            "this export"),
        },
        "annotations": {
            "confidence": ("uncalibrated: checkpoint ships invalid temperatures "
                           "clamped to [0.5,5] (SDK warning) and README reports "
                           "ECE 0.213 over-confidence; probabilities/choices are "
                           "model-defined, not correctness"),
            "escalate_driver": ("tool_gate escalates are model 'uncertain' "
                                "choices on harvest-truncated tool text "
                                "(500-char args_summary, no assistant framing), "
                                "not detected conflicts; 'allow' rows are "
                                "no_active_intent_constraint"),
        },
        "timing": {"wall_seconds": wall,
                   "note": ("wall_seconds measures THIS process only; on a "
                            "cache-resumed run it is the resume time, not the "
                            "original compute time (first full pass of this "
                            "pilot: 386.64s)"),
                   "batch_ms_min_med_max": [batch_ms[0], batch_ms[len(batch_ms)//2],
                                            batch_ms[-1]] if batch_ms else []},
        "job_accounting": {"planned": len(phase1_jobs) + len(phase2_jobs),
                           "emitted": len(all_rows),
                           "complete": len(all_rows) ==
                                       len(phase1_jobs) + len(phase2_jobs)},
        "tool_verdicts": _tally([r for r in aggregates
                                 if r.get("record_type") == "tool_gate_aggregate"],
                                "verdict", "reason_code"),
        "choice_distribution": _choices(all_rows),
        "gate_outcomes": _tally(aggregates, "record_type", "recommended_route"),
        "job_status": _tally(all_rows, "gate", "status"),
        "next_action": ("corpus-host access, then the full 81-file blind replay "
                        "via `runner.py run`"),
    }
    runner._write_json_atomic(args.output / "pilot-receipt.json", summary)
    print(json.dumps({k: summary[k] for k in
                      ("record_type", "label", "scope", "structural_limits",
                       "annotations", "timing", "job_accounting", "tool_verdicts",
                       "choice_distribution", "gate_outcomes", "job_status")},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
