#!/usr/bin/env python3
"""Laya-only, versioned DAG replay for raw Claude Code transcripts.

Phase 1 scores atomic user-intent spans, every earlier-user-message pair, and
assistant prose boundaries. The deterministic reducer then constructs as-of
pin snapshots and phase-2 acknowledgment, plan, research, and tool checks.
Independent jobs fan out to a bounded pool of local Laya workers; only this
process reduces outputs chronologically. No historic tool is executed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import multiprocessing as mp
import os
import queue
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


HERE = Path(__file__).resolve().parent
SCRIPT_ROOT = HERE.parents[1]
MODULE_ROOT = SCRIPT_ROOT.parent
PROFILE_PATH = MODULE_ROOT / "profiles" / "laya-typed-decisions" / "v1" / "profile.json"
sys.path.insert(0, str(SCRIPT_ROOT))
sys.path.insert(0, str(HERE))

from replay_core import compact_retention, hard_deny_reason  # noqa: E402
from replay_sources import (  # noqa: E402
    REPLAY_EVENT_CONTRACT_VERSION,
    ReplayEvent,
    SourceLocation,
    SourceIntegrityError,
    SourceReport,
    load_claude_jsonl,
    public_summary,
)
from worker import worker_main  # noqa: E402


EVENT_CONTRACT_VERSION = 1
PIN_GATE_CONTRACT_VERSION = 2
ACKNOWLEDGMENT_GATE_CONTRACT_VERSION = 1
ASSISTANT_BOUNDARY_GATE_CONTRACT_VERSION = 1
EVENT_REQUIRED_FIELDS = frozenset({
    "event_id", "stream_id", "session_id", "sequence", "timestamp", "kind",
    "authority", "source", "uuid", "parent_uuid", "is_sidechain", "agent_id",
    "tool_use_id", "text", "metadata",
})
_RESEARCH_TOOLS = frozenset({"read", "webfetch", "websearch", "grep", "glob"})
_STOPWORDS = frozenset({
    "about", "after", "again", "also", "because", "before", "being", "could",
    "does", "from", "have", "into", "just", "more", "should", "that", "their",
    "there", "these", "they", "this", "through", "using", "what", "when", "where",
    "which", "while", "with", "would", "your", "the", "and", "for", "are", "was",
    "were", "will", "then", "than", "have", "has", "had", "not", "but", "all",
})


class AdapterError(RuntimeError):
    """A version, coverage, or run identity check failed."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _hash_id(value: str) -> str:
    return _sha(value.encode("utf-8"))


def _safe_int(value: Any, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise AdapterError("invalid_profile_integer")
    return value


def load_profile(path: Path = PROFILE_PATH) -> Dict[str, Any]:
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError("profile_read_or_parse_failed") from exc
    if not isinstance(profile, dict) or profile.get("schema_version") != 1:
        raise AdapterError("profile_schema_version_unsupported")
    if profile.get("shared_event_contract", {}).get("version") != EVENT_CONTRACT_VERSION:
        raise AdapterError("profile_event_contract_version_mismatch")
    if REPLAY_EVENT_CONTRACT_VERSION != EVENT_CONTRACT_VERSION:
        raise AdapterError("shared_event_contract_version_mismatch")
    if profile.get("pin_gate_contract", {}).get("version") != PIN_GATE_CONTRACT_VERSION:
        raise AdapterError("pin_gate_contract_version_mismatch")
    if profile.get("acknowledgment_gate_contract", {}).get("version") != ACKNOWLEDGMENT_GATE_CONTRACT_VERSION:
        raise AdapterError("acknowledgment_gate_contract_version_mismatch")
    if profile.get("assistant_boundary_gate_contract", {}).get("version") != ASSISTANT_BOUNDARY_GATE_CONTRACT_VERSION:
        raise AdapterError("assistant_boundary_gate_contract_version_mismatch")
    model = profile.get("model", {})
    if model.get("sdk_version") != "0.3.20" or not model.get("sdk_revision"):
        raise AdapterError("profile_sdk_identity_invalid")
    inference = profile.get("inference", {})
    for name in ("max_len", "head_max_len", "max_options_per_question", "state_chunk_tokens",
                 "state_chunk_overlap_tokens", "max_research_pairs_per_boundary", "batch_size",
                 "workers", "torch_threads_per_worker", "max_queued_batches_per_worker"):
        _safe_int(inference.get(name))
    for question in profile.get("questions", {}).values():
        choices = question.get("criteria") if isinstance(question, dict) else None
        if not isinstance(choices, dict) or not choices:
            raise AdapterError("profile_question_choices_invalid")
        if len(choices) > inference["max_options_per_question"]:
            raise AdapterError("profile_question_exceeds_option_limit")
    return profile


def profile_fingerprint(profile: Mapping[str, Any]) -> str:
    """Bind a run to Laya v1 code and only the shared contracts it consumes."""
    files = {
        "profile": _file_sha(PROFILE_PATH),
        "runner": _file_sha(Path(__file__)),
        "worker": _file_sha(HERE / "worker.py"),
        "event_parser": _file_sha(SCRIPT_ROOT / "replay_sources.py"),
        "hard_deny_and_compaction": _file_sha(SCRIPT_ROOT / "replay_core.py"),
    }
    return _sha(_canonical({"profile": profile, "files": files,
                            "event_contract_version": EVENT_CONTRACT_VERSION,
                            "pin_gate_contract_version": PIN_GATE_CONTRACT_VERSION,
                            "acknowledgment_gate_contract_version":
                                ACKNOWLEDGMENT_GATE_CONTRACT_VERSION,
                            "assistant_boundary_gate_contract_version":
                                ASSISTANT_BOUNDARY_GATE_CONTRACT_VERSION}))


def verify_event_contract() -> None:
    names = {field for field in getattr(ReplayEvent, "__dataclass_fields__", {})}
    if not EVENT_REQUIRED_FIELDS.issubset(names):
        raise AdapterError("shared_event_contract_fields_mismatch")
    if REPLAY_EVENT_CONTRACT_VERSION != EVENT_CONTRACT_VERSION:
        raise AdapterError("shared_event_contract_version_mismatch")


def _stream_groups(events: Sequence[ReplayEvent]) -> Dict[str, List[ReplayEvent]]:
    groups: Dict[str, List[ReplayEvent]] = defaultdict(list)
    for event in events:
        groups[event.stream_id].append(event)
    return {key: sorted(rows, key=lambda item: (item.sequence, item.event_id))
            for key, rows in sorted(groups.items())}


def _stream_order(streams: Mapping[str, Sequence[ReplayEvent]]) -> Tuple[List[str], set[str]]:
    """Topologically place resolved child streams after their parent stream."""
    children = {key for key, rows in streams.items() if any(row.is_sidechain for row in rows)}
    parent_for: Dict[str, Optional[str]] = {}
    for key in children:
        first = next((row for row in streams[key]
                      if row.is_sidechain and row.kind == "delegated_prompt"), None)
        parent_for[key] = (first.metadata.get("delegated_from_stream_id") if first else None)
    ordered = sorted(set(streams) - children)
    pending = set(children)
    unresolved: set[str] = set()
    while pending:
        ready = sorted(key for key in pending if parent_for.get(key) in ordered)
        if not ready:
            unresolved.update(pending)
            ordered.extend(sorted(pending))
            break
        ordered.extend(ready)
        pending.difference_update(ready)
    return ordered, unresolved


def _atomize(text: str, tokenizer: Any, max_tokens: int,
             overlap_tokens: int = 32) -> List[Dict[str, Any]]:
    """Split text into sentence-aware overlapping windows with exact offsets."""
    if not text:
        return [{"index": 0, "start": 0, "end": 0, "text": "", "token_count": 0}]
    try:
        encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        token_ids = encoded["input_ids"]
        offsets = encoded["offset_mapping"]
    except (TypeError, KeyError, ValueError) as exc:
        raise AdapterError("tokenizer_offsets_unavailable") from exc
    if len(token_ids) != len(offsets):
        raise AdapterError("tokenizer_offsets_length_mismatch")
    if not token_ids:
        return [{"index": 0, "start": 0, "end": len(text), "text": text, "token_count": 0}]
    if overlap_tokens < 0 or overlap_tokens >= max_tokens:
        raise AdapterError("invalid_chunk_overlap")
    boundaries = []
    for match in re.finditer(r"(?<=[.!?])(?:[\"')\]]*)\s+|\n+", text):
        boundary_char = match.end()
        token_index = next((i for i, pair in enumerate(offsets)
                            if int(pair[0]) >= boundary_char), None)
        if token_index is not None:
            boundaries.append(token_index)
    atoms: List[Dict[str, Any]] = []
    token_start = 0
    while token_start < len(token_ids):
        hard_end = min(len(token_ids), token_start + max_tokens)
        candidates = [point for point in boundaries
                      if token_start < point <= hard_end
                      and point - token_start >= max(32, max_tokens // 2)]
        token_end = max(candidates) if candidates else hard_end
        if token_end <= token_start:
            raise AdapterError("tokenizer_chunk_made_no_progress")
        start = 0 if token_start == 0 else int(offsets[token_start][0])
        end = len(text) if token_end == len(token_ids) else int(offsets[token_end][0])
        atoms.append({"index": len(atoms), "start": start, "end": end,
                      "text": text[start:end], "token_count": token_end - token_start,
                      "token_start": token_start, "token_end": token_end})
        if token_end == len(token_ids):
            break
        next_start = max(token_start + 1, token_end - overlap_tokens)
        if next_start <= token_start:
            raise AdapterError("tokenizer_chunk_overlap_made_no_progress")
        token_start = next_start
    if not atoms or atoms[0]["start"] != 0 or atoms[-1]["end"] != len(text):
        raise AdapterError("tokenizer_atomization_incomplete_coverage")
    if any(left["end"] < right["start"] for left, right in zip(atoms, atoms[1:])):
        raise AdapterError("tokenizer_atomization_gap")
    if any(atom["token_count"] > max_tokens for atom in atoms):
        raise AdapterError("tokenizer_atom_exceeds_profile_budget")
    return atoms


def _span_id(event_id: str, atom: Mapping[str, Any]) -> str:
    return f"{event_id}#chars-{atom['start']}-{atom['end']}"


def _stable_job_id(run_id: str, profile_hash: str, request_hash: str,
                   metadata: Mapping[str, Any]) -> str:
    stable = {key: metadata.get(key) for key in (
        "gate", "stream_id", "event_id", "prior_event_id", "span_id",
        "prior_span_id", "current_span_id", "pin_id", "pin_source_event_id",
        "claim_span", "claim_source_event_id", "evidence_event_id", "evidence_span", "tool_span",
        "user_span_id", "response_event_id", "response_span_id", "plan_span_id",
    )}
    return _sha(_canonical({"run_id": run_id, "profile_hash": profile_hash,
                            "request_hash": request_hash, "metadata": stable}))


def _make_job(run_id: str, profile_hash: str, profile: Mapping[str, Any],
              group: str, gate: str, event: ReplayEvent, state: Mapping[str, Any],
              **metadata: Any) -> Dict[str, Any]:
    questions = profile["questions"]
    question_ids = profile["question_groups"].get(group)
    if not isinstance(question_ids, list) or not question_ids:
        raise AdapterError("unknown_question_group")
    definitions = {qid: questions[qid] for qid in question_ids}
    request_hash = _sha(_canonical({
        "profile_hash": profile_hash,
        "model_revision": profile["model"]["revision"],
        "sdk_revision": profile["model"]["sdk_revision"],
        "question_group": group,
        "questions": definitions,
        "state": state,
    }))
    public_meta: Dict[str, Any] = {
        "gate": gate,
        "question_group": group,
        "run_id": run_id,
        "adapter_id": profile.get("adapter_id"),
        "stream_id": event.stream_id,
        "event_id": event.event_id,
        "source_file_sha256": event.source.file_sha256,
        "source_line": event.source.line,
        "source_timestamp": event.timestamp,
        "adapter_version": profile.get("adapter_version"),
        "profile_version": profile.get("profile_version"),
    }
    public_meta.update(metadata)
    job_id = _stable_job_id(run_id, profile_hash, request_hash, public_meta)
    return {"job_id": job_id, "request_hash": request_hash,
            "questions": definitions, "state": dict(state), "meta": public_meta}


def _sanitize_answers(answers: Any, question_group: str,
                      profile: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(answers, Mapping):
        raise AdapterError("model_answer_payload_invalid")
    expected = profile["question_groups"][question_group]
    if set(answers) != set(expected):
        raise AdapterError("model_question_set_mismatch")
    clean: Dict[str, Any] = {}
    for qid in expected:
        value = answers[qid]
        if not isinstance(value, Mapping):
            raise AdapterError("model_answer_not_object")
        labels = set(profile["questions"][qid]["criteria"])
        choice = value.get("choice")
        probs = value.get("probabilities")
        if not isinstance(choice, str) or choice not in labels:
            raise AdapterError("model_answer_choice_invalid")
        if not isinstance(probs, Mapping) or set(probs) != labels:
            raise AdapterError("model_probability_keys_invalid")
        safe_probs: Dict[str, float] = {}
        for key, raw in probs.items():
            if not isinstance(raw, (int, float)) or not math.isfinite(float(raw)) or float(raw) < 0:
                raise AdapterError("model_probability_value_invalid")
            safe_probs[str(key)] = float(raw)
        if abs(sum(safe_probs.values()) - 1.0) > 0.02:
            raise AdapterError("model_probabilities_not_normalized")
        clean[qid] = {
            "choice": choice,
            "probabilities": dict(sorted(safe_probs.items())),
            "confidence": value.get("confidence"),
            "answer_confidence": value.get("answer_confidence"),
        }
    return clean


class _OutputCache:
    """Private cache stores model labels/scores only; request content is hashed."""
    def __init__(self, path: Path) -> None:
        created_parent = not path.parent.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "posix" and created_parent:
            path.parent.chmod(0o700)
        self.connection = sqlite3.connect(path, timeout=60)
        if os.name == "posix" and path.exists():
            path.chmod(0o600)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS outputs (request_hash TEXT PRIMARY KEY, result_json TEXT NOT NULL)"
        )
        self.connection.commit()

    def get(self, request_hash: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT result_json FROM outputs WHERE request_hash = ?", (request_hash,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, request_hash: str, result: Mapping[str, Any]) -> None:
        payload = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.connection.execute(
            "INSERT OR IGNORE INTO outputs(request_hash, result_json) VALUES (?, ?)",
            (request_hash, payload),
        )
        self.connection.commit()

    def put_many(self, rows: Sequence[Tuple[str, Mapping[str, Any]]]) -> None:
        if not rows:
            return
        payloads = [
            (request_hash, json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            for request_hash, result in rows
        ]
        self.connection.executemany(
            "INSERT OR IGNORE INTO outputs(request_hash, result_json) VALUES (?, ?)", payloads
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


class _WorkerPool:
    """Bounded CPU worker pool; every worker owns one identical Laya snapshot."""
    def __init__(self, model_path: Path, profile: Mapping[str, Any], workers: int) -> None:
        self.ctx = mp.get_context("spawn")
        inference = profile["inference"]
        model = profile["model"]
        self.max_queued = int(inference["max_queued_batches_per_worker"])
        self.batch_size = int(inference["batch_size"])
        self.result_queue = self.ctx.Queue()
        self.task_queues = [self.ctx.Queue(maxsize=self.max_queued) for _ in range(workers)]
        self.processes = []
        for worker_id in range(workers):
            process = self.ctx.Process(
                target=worker_main,
                args=(worker_id, str(model_path), model["revision"], model["sdk_version"],
                      model["sdk_revision"],
                      int(inference["torch_threads_per_worker"]), int(inference["max_len"]),
                      int(inference["head_max_len"]), self.task_queues[worker_id], self.result_queue),
                name=f"laya-v1-worker-{worker_id}",
            )
            process.start()
            self.processes.append(process)
        self.worker_count = workers
        self.ready: Dict[int, Dict[str, Any]] = {}

    def wait_ready(self, timeout_s: int = 900) -> List[Dict[str, Any]]:
        deadline = time.monotonic() + timeout_s
        failures: List[str] = []
        while len(self.ready) < self.worker_count and time.monotonic() < deadline:
            try:
                message = self.result_queue.get(timeout=2)
            except queue.Empty:
                dead = [index for index, proc in enumerate(self.processes)
                        if not proc.is_alive() and index not in self.ready]
                if dead:
                    failures.append("worker_process_exited")
                    break
                continue
            if message.get("kind") == "worker_ready":
                self.ready[int(message["worker_id"])] = message
            elif message.get("kind") == "worker_start_failed":
                failures.append(str(message.get("reason_code", "worker_start_failed")))
                break
        if failures or len(self.ready) != self.worker_count:
            self.close()
            raise AdapterError("worker_pool_start_failed:" + (failures[0] if failures else "timeout"))
        return [self.ready[index] for index in sorted(self.ready)]

    def infer(self, jobs: Sequence[Dict[str, Any]], profile: Mapping[str, Any],
              cache: _OutputCache, existing: Mapping[str, Dict[str, Any]],
              append_receipt: Any, *, run_id: str, profile_hash: str) -> Dict[str, Dict[str, Any]]:
        """Run jobs in schema-homogeneous batches; return content-free results."""
        inferred: Dict[str, Dict[str, Any]] = {}
        pending_by_group: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for job in sorted(jobs, key=lambda item: item["job_id"]):
            job_id = job["job_id"]
            prior = existing.get(job_id)
            if prior is not None:
                if prior.get("request_sha256") != job["request_hash"]:
                    raise AdapterError("resume_request_hash_mismatch")
                inferred[job_id] = prior
                continue
            cached = cache.get(job["request_hash"])
            if cached is not None:
                row = self._receipt_row(job, cached, run_id, profile_hash,
                                        worker_id=None, batch_id=None, cached=True)
                append_receipt(row)
                inferred[job_id] = row
                continue
            pending_by_group[job["meta"]["question_group"]].append(job)

        batch_tasks: List[Dict[str, Any]] = []
        for group, grouped_jobs in sorted(pending_by_group.items()):
            questions = profile["questions"]
            qdefs = {qid: questions[qid] for qid in profile["question_groups"][group]}
            for offset in range(0, len(grouped_jobs), self.batch_size):
                batch_jobs = grouped_jobs[offset:offset + self.batch_size]
                batch_id = _sha(_canonical([job["job_id"] for job in batch_jobs]))
                batch_tasks.append({"batch_id": batch_id, "group": group,
                                    "jobs": batch_jobs, "questions": qdefs})

        max_inflight = self.worker_count * self.max_queued
        next_batch = 0
        inflight: Dict[str, Dict[str, Any]] = {}
        next_worker = 0
        complete_batches = 0
        while next_batch < len(batch_tasks) or inflight:
            while next_batch < len(batch_tasks) and len(inflight) < max_inflight:
                batch = batch_tasks[next_batch]
                wid = next_worker % self.worker_count
                next_worker += 1
                envelope = {"batch_id": batch["batch_id"],
                            "questions": batch["questions"],
                            "jobs": [{"job_id": job["job_id"], "state": job["state"]}
                                     for job in batch["jobs"]],
                            "enqueued_monotonic": time.monotonic()}
                self.task_queues[wid].put(envelope)
                inflight[batch["batch_id"]] = {**batch, "worker_id": wid,
                                               "enqueued_monotonic": envelope["enqueued_monotonic"]}
                next_batch += 1
            try:
                message = self.result_queue.get(timeout=900)
            except queue.Empty as exc:
                raise AdapterError("worker_batch_timeout") from exc
            if message.get("kind") not in {"batch_result", "batch_failed"}:
                # Startup messages are consumed by wait_ready; anything else
                # is an invalid worker protocol message.
                raise AdapterError("worker_protocol_message_invalid")
            batch_id = str(message.get("batch_id", ""))
            batch = inflight.pop(batch_id, None)
            if batch is None:
                raise AdapterError("unknown_worker_batch_id")
            worker_id = int(message.get("worker_id", -1))
            batch_elapsed = message.get("batch_elapsed_ms")
            batch_by_job = {job["job_id"]: job for job in batch["jobs"]}
            if message["kind"] == "batch_failed":
                rows = [{"job_id": job["job_id"], "status": "failed",
                         "reason_codes": [str(message.get("reason_code", "batch_failed"))],
                         "token_preflight": None, "answers": None,
                         "batch_elapsed_ms": None, "amortized_item_ms": None}
                        for job in batch["jobs"]]
            else:
                rows = message.get("rows", [])
                if not isinstance(rows, list) or len(rows) != len(batch["jobs"]):
                    raise AdapterError("worker_batch_result_count_mismatch")
            queued_ms = max(0.0, (time.monotonic() - batch["enqueued_monotonic"]) * 1000.0)
            cache_rows: List[Tuple[str, Mapping[str, Any]]] = []
            for result in rows:
                job = batch_by_job.get(str(result.get("job_id", "")))
                if job is None:
                    raise AdapterError("worker_returned_unknown_job")
                output = dict(result)
                output["batch_id"] = batch_id
                output["worker_id"] = worker_id
                output["queue_wait_ms"] = round(queued_ms, 3)
                output["cached"] = False
                if output.get("status") == "scored":
                    try:
                        output["answers"] = _sanitize_answers(
                            output.get("answers"), job["meta"]["question_group"], profile)
                        cache_rows.append((job["request_hash"], {
                            "status": "scored", "answers": output["answers"],
                            "token_preflight": output.get("token_preflight"),
                        }))
                    except AdapterError as exc:
                        output["status"] = "failed"
                        output["reason_codes"] = [str(exc).split(":", 1)[0]]
                        output["answers"] = None
                receipt = self._receipt_row(job, output, run_id, profile_hash,
                                            worker_id=worker_id, batch_id=batch_id,
                                            cached=False)
                append_receipt(receipt)
                inferred[job["job_id"]] = receipt
            cache.put_many(cache_rows)
            complete_batches += 1
            if complete_batches % 25 == 0 or complete_batches == len(batch_tasks):
                print(json.dumps({"phase": "model_jobs", "done_batches": complete_batches,
                                  "planned_batches": len(batch_tasks),
                                  "completed_jobs": len(inferred)}, sort_keys=True), flush=True)
        return inferred

    @staticmethod
    def _receipt_row(job: Mapping[str, Any], result: Mapping[str, Any],
                     run_id: str, profile_hash: str, *, worker_id: Optional[int],
                     batch_id: Optional[str], cached: bool) -> Dict[str, Any]:
        meta = job["meta"]
        preflight = result.get("token_preflight")
        if isinstance(preflight, dict):
            preflight = {key: value for key, value in preflight.items()
                         if key != "reason_codes"}
        return {
            "schema_version": 1,
            "record_type": "decision_job",
            "run_id": run_id,
            "adapter_id": meta.get("adapter_id", "laya-typed-decisions-dag"),
            "adapter_version": meta.get("adapter_version"),
            "profile_version": meta.get("profile_version"),
            "profile_sha256": profile_hash,
            "job_id": job["job_id"],
            "request_sha256": job["request_hash"],
            "gate": meta["gate"],
            "question_group": meta["question_group"],
            "stream_sha256": _hash_id(str(meta["stream_id"])),
            "event_id": meta["event_id"],
            "prior_event_id": meta.get("prior_event_id"),
            "span_id": meta.get("span_id"),
            "prior_span_id": meta.get("prior_span_id"),
            "current_span_id": meta.get("current_span_id"),
            "pin_id": meta.get("pin_id"),
            "pin_source_event_id": meta.get("pin_source_event_id"),
            "claim_span": meta.get("claim_span"),
            "claim_source_event_id": meta.get("claim_source_event_id"),
            "claim_source_file_sha256": meta.get("claim_source_file_sha256"),
            "claim_source_line": meta.get("claim_source_line"),
            "evidence_event_id": meta.get("evidence_event_id"),
            "evidence_span": meta.get("evidence_span"),
            "tool_span": meta.get("tool_span"),
            "pin_char_span": meta.get("pin_char_span"),
            "prior_char_span": meta.get("prior_char_span"),
            "current_char_span": meta.get("current_char_span"),
            "source_file_sha256": meta.get("source_file_sha256"),
            "source_line": meta.get("source_line"),
            "source_timestamp": meta.get("source_timestamp"),
            "user_span_id": meta.get("user_span_id"),
            "user_char_span": meta.get("user_char_span"),
            "plan_span_id": meta.get("plan_span_id"),
            "plan_char_span": meta.get("plan_char_span"),
            "response_event_id": meta.get("response_event_id"),
            "response_span_id": meta.get("response_span_id"),
            "response_char_span": meta.get("response_char_span"),
            "response_source_file_sha256": meta.get("response_source_file_sha256"),
            "response_source_line": meta.get("response_source_line"),
            "response_timestamp": meta.get("response_timestamp"),
            "claim_timestamp": meta.get("claim_timestamp"),
            "evidence_timestamp": meta.get("evidence_timestamp"),
            "prior_source_file_sha256": meta.get("prior_source_file_sha256"),
            "prior_source_line": meta.get("prior_source_line"),
            "evidence_source_file_sha256": meta.get("evidence_source_file_sha256"),
            "evidence_source_line": meta.get("evidence_source_line"),
            "prior_timestamp": meta.get("prior_timestamp"),
            "current_timestamp": meta.get("current_timestamp"),
            "status": result.get("status"),
            "reason_codes": result.get("reason_codes", []),
            "answers": result.get("answers"),
            "token_preflight": preflight,
            "batch_id": batch_id or result.get("batch_id"),
            "worker_id": worker_id if worker_id is not None else result.get("worker_id"),
            "batch_size": result.get("batch_size"),
            "batch_elapsed_ms": result.get("batch_elapsed_ms"),
            "amortized_item_ms": result.get("amortized_item_ms"),
            "queue_wait_ms": result.get("queue_wait_ms"),
            "cached": cached,
            "created_at": _now(),
        }

    def close(self) -> None:
        for task_queue in getattr(self, "task_queues", []):
            try:
                task_queue.put_nowait(None)
            except Exception:
                pass
        for process in getattr(self, "processes", []):
            process.join(timeout=15)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        for task_queue in getattr(self, "task_queues", []):
            try:
                task_queue.close()
            except Exception:
                pass
        try:
            self.result_queue.close()
        except Exception:
            pass


def _existing_receipts(path: Path) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    if not path.exists():
        return rows
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            row = json.loads(raw)
            if row.get("record_type") == "decision_job" and row.get("job_id"):
                job_id = str(row["job_id"])
                prior = rows.get(job_id)
                if prior and prior.get("request_sha256") != row.get("request_sha256"):
                    raise AdapterError("conflicting_duplicate_receipt_job")
                rows[job_id] = row
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError("existing_receipt_unreadable") from exc
    return rows


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        if os.name == "posix":
            os.chmod(path, 0o600)
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        handle.write("\n")
        handle.flush()


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        path.parent.chmod(0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                   encoding="utf-8")
    if os.name == "posix":
        os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _public_source_manifest(report: SourceReport) -> Dict[str, Any]:
    entries = [{"path_id": key, "sha256": value}
               for key, value in sorted(report.source_hashes.items())]
    return {"files": report.files, "source_hashes": entries,
            "source_manifest_sha256": _sha(_canonical(entries))}


def _verify_full_corpus(events: Sequence[ReplayEvent], report: SourceReport) -> None:
    if report.files != 81:
        raise AdapterError("source_must_be_the_verified_81_file_corpus")
    if report.malformed_rows:
        raise AdapterError("malformed_source_rows_present")
    if len(events) != 18350:
        raise AdapterError("normalized_event_count_mismatch")
    summary = public_summary(list(events), report)
    if summary.get("streams") != 80 or summary.get("events_by_kind", {}).get("human_user") != 198:
        raise AdapterError("source_public_coverage_mismatch")


def _event_atoms(events: Sequence[ReplayEvent], tokenizer: Any,
                 max_tokens: int, overlap_tokens: int = 32) -> Dict[str, List[Dict[str, Any]]]:
    return {event.event_id: _atomize(event.text, tokenizer, max_tokens, overlap_tokens)
            for event in events
            if ((event.kind == "human_user" and event.authority == "human")
                or (event.kind == "assistant_text" and event.authority == "agent"))}


def _phase1_jobs(run_id: str, profile_hash: str, profile: Mapping[str, Any],
                 streams: Mapping[str, Sequence[ReplayEvent]],
                 atoms_by_event: Mapping[str, Sequence[Mapping[str, Any]]]) -> Tuple[List[Dict[str, Any]], int]:
    jobs: List[Dict[str, Any]] = []
    expected_message_pairs = 0
    for stream_id, rows in streams.items():
        users = [event for event in rows if event.kind == "human_user" and event.authority == "human"]
        for current_index, current in enumerate(users):
            current_atoms = atoms_by_event[current.event_id]
            for atom in current_atoms:
                span_id = _span_id(current.event_id, atom)
                jobs.append(_make_job(
                    run_id, profile_hash, profile, "user_pin_status", "user_pin_status",
                    current, {"human_message_span": atom["text"],
                              "human_message_timestamp": current.timestamp},
                    span_id=span_id, char_span=[atom["start"], atom["end"]],
                ))
            for prior_index, prior in enumerate(users[:current_index]):
                expected_message_pairs += 1
                for prior_atom in atoms_by_event[prior.event_id]:
                    for current_atom in current_atoms:
                        prior_span = _span_id(prior.event_id, prior_atom)
                        current_span = _span_id(current.event_id, current_atom)
                        jobs.append(_make_job(
                            run_id, profile_hash, profile, "user_message_pair", "user_message_relation",
                            current,
                            {"earlier_user_excerpt": prior_atom["text"],
                             "later_user_excerpt": current_atom["text"],
                             "earlier_user_timestamp": prior.timestamp,
                             "later_user_timestamp": current.timestamp},
                            prior_event_id=prior.event_id,
                            prior_source_file_sha256=prior.source.file_sha256,
                            prior_source_line=prior.source.line,
                            prior_span_id=prior_span, current_span_id=current_span,
                            prior_char_span=[prior_atom["start"], prior_atom["end"]],
                            current_char_span=[current_atom["start"], current_atom["end"]],
                            prior_timestamp=prior.timestamp,
                            current_timestamp=current.timestamp,
                            pair_index=prior_index,
                        ))
        for assistant_event in rows:
            if assistant_event.kind != "assistant_text" or assistant_event.authority != "agent":
                continue
            for atom in atoms_by_event[assistant_event.event_id]:
                span_id = _span_id(assistant_event.event_id, atom)
                jobs.append(_make_job(
                    run_id, profile_hash, profile, "assistant_boundary_pair",
                    "assistant_boundary", assistant_event,
                    {"assistant_text_span": atom["text"],
                     "assistant_timestamp": assistant_event.timestamp},
                    span_id=span_id, char_span=[atom["start"], atom["end"]],
                ))
    return jobs, expected_message_pairs


def _relation_aggregates(jobs: Sequence[Dict[str, Any]],
                         results: Mapping[str, Mapping[str, Any]]) -> Tuple[Dict[Tuple[str, str, str], List[Dict[str, Any]]], Dict[str, int]]:
    grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    stats = {"expected_user_event_pairs": 0, "relation_jobs": 0,
             "relation_job_scored": 0, "relation_job_incomplete": 0}
    unique_pairs: set[Tuple[str, str]] = set()
    for job in jobs:
        meta = job["meta"]
        if meta["gate"] != "user_message_relation":
            continue
        key = (meta["stream_id"], meta["prior_event_id"], meta["event_id"])
        grouped[key].append(dict(meta, job_id=job["job_id"]))
        unique_pairs.add((meta["prior_event_id"], meta["event_id"]))
        stats["relation_jobs"] += 1
        result = results.get(job["job_id"])
        if result and result.get("status") == "scored":
            stats["relation_job_scored"] += 1
        else:
            stats["relation_job_incomplete"] += 1
    stats["expected_user_event_pairs"] = len(unique_pairs)
    return grouped, stats


def _pin_statuses(jobs: Sequence[Dict[str, Any]],
                  results: Mapping[str, Mapping[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    statuses: Dict[str, Dict[str, Any]] = {}
    stats = {"pin_status_jobs": 0, "pin_status_scored": 0, "pin_status_incomplete": 0,
             "ack_expectation_required": 0, "ack_expectation_not_required": 0,
             "ack_expectation_unclear": 0}
    for job in jobs:
        meta = job["meta"]
        if meta["gate"] != "user_pin_status":
            continue
        stats["pin_status_jobs"] += 1
        result = results.get(job["job_id"])
        if result and result.get("status") == "scored" and result.get("answers"):
            status = result["answers"]["pin_status"]["choice"]
            ack_expectation = result["answers"]["ack_expectation"]["choice"]
            stats["pin_status_scored"] += 1
        else:
            status = "unclear"
            ack_expectation = "unclear"
            stats["pin_status_incomplete"] += 1
        stats[f"ack_expectation_{ack_expectation}"] += 1
        statuses[meta["span_id"]] = {
            "status": status,
            "ack_expectation": ack_expectation,
            "event_id": meta["event_id"],
            "span_id": meta["span_id"],
            "char_span": meta["char_span"],
            "job_id": job["job_id"],
            "source_file_sha256": meta["source_file_sha256"],
            "source_line": meta["source_line"],
            "scored": status != "unclear" or (result and result.get("status") == "scored"),
        }
    return statuses, stats


def _assistant_boundary_statuses(
        jobs: Sequence[Dict[str, Any]],
        results: Mapping[str, Mapping[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    statuses: Dict[str, Dict[str, Any]] = {}
    stats = {"assistant_boundary_jobs": 0, "assistant_boundary_scored": 0,
             "assistant_boundary_incomplete": 0}
    for job in jobs:
        meta = job["meta"]
        if meta["gate"] != "assistant_boundary":
            continue
        stats["assistant_boundary_jobs"] += 1
        result = results.get(job["job_id"])
        if result and result.get("status") == "scored" and result.get("answers"):
            choice = result["answers"]["assistant_boundary"]["choice"]
            scored = True
            stats["assistant_boundary_scored"] += 1
        else:
            choice = "unclear"
            scored = False
            stats["assistant_boundary_incomplete"] += 1
        statuses[meta["span_id"]] = {
            "status": choice, "event_id": meta["event_id"],
            "span_id": meta["span_id"], "char_span": meta["char_span"],
            "job_id": job["job_id"],
            "source_file_sha256": meta["source_file_sha256"],
            "source_line": meta["source_line"],
            "scored": scored,
        }
    return statuses, stats


def _next_assistant_response_events(user_event: ReplayEvent,
                                    rows: Sequence[ReplayEvent]) -> List[ReplayEvent]:
    """Return text blocks from only the next assistant message before the next user turn."""
    start = next((index for index, item in enumerate(rows)
                  if item.event_id == user_event.event_id), None)
    if start is None:
        return []
    first: Optional[ReplayEvent] = None
    for item in rows[start + 1:]:
        if item.kind == "human_user" and item.authority == "human":
            break
        if item.kind == "assistant_text" and item.authority == "agent":
            first = item
            break
    if first is None:
        return []
    return [item for item in rows[start + 1:]
            if item.kind == "assistant_text" and item.authority == "agent"
            and item.source.file_sha256 == first.source.file_sha256
            and item.source.line == first.source.line
            and item.uuid == first.uuid]


def _acknowledgment_jobs(run_id: str, profile_hash: str,
                         profile: Mapping[str, Any], user_event: ReplayEvent,
                         rows: Sequence[ReplayEvent],
                         atoms: Sequence[Mapping[str, Any]],
                         status_by_span: Mapping[str, Mapping[str, Any]],
                         tokenizer: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    """Plan exact user-span/next-response chunk pairs and explicit omission records."""
    jobs: List[Dict[str, Any]] = []
    plans: List[Dict[str, Any]] = []
    stats = {"ack_spans_seen": len(atoms), "ack_spans_required": 0,
             "ack_spans_not_required": 0, "ack_spans_incomplete": 0,
             "ack_spans_missing_response": 0, "ack_response_jobs": 0}
    response_events = _next_assistant_response_events(user_event, rows)
    response_atoms = [
        (response_event, atom)
        for response_event in response_events
        for atom in _atomize(
            response_event.text, tokenizer,
            int(profile["inference"]["state_chunk_tokens"]),
            int(profile["inference"]["state_chunk_overlap_tokens"]),
        )
    ]
    for atom in atoms:
        span_id = _span_id(user_event.event_id, atom)
        pin = status_by_span.get(span_id, {})
        pin_status = str(pin.get("status", "unclear"))
        expectation = str(pin.get("ack_expectation", "unclear"))
        scored = bool(pin.get("scored"))
        required = pin_status == "durable_assertion" or expectation == "required"
        plan: Dict[str, Any] = {
            "schema_version": 1, "record_type": "acknowledgment_gate_plan",
            "run_id": run_id, "profile_sha256": profile_hash,
            "stream_sha256": _hash_id(user_event.stream_id),
            "event_id": user_event.event_id, "span_id": span_id,
            "source_file_sha256": user_event.source.file_sha256,
            "source_line": user_event.source.line,
            "source_timestamp": user_event.timestamp,
            "pin_status": pin_status, "ack_expectation": expectation,
            "ack_required": required, "response_event_ids": [item.event_id for item in response_events],
            "status": "planned", "planned_job_count": 0, "planned_job_ids": [],
        }
        if not scored or pin_status == "unclear" or expectation == "unclear":
            plan.update({"status": "incomplete", "reason_code": "intent_or_ack_expectation_unclear",
                         "recommended_route": "escalate"})
            stats["ack_spans_incomplete"] += 1
        elif not required:
            plan.update({"status": "not_required", "recommended_route": None})
            stats["ack_spans_not_required"] += 1
        elif not response_events:
            plan.update({"status": "omitted", "reason_code": "no_next_assistant_response",
                         "recommended_route": "reconfirm_intent"})
            stats["ack_spans_required"] += 1
            stats["ack_spans_missing_response"] += 1
        elif not response_atoms:
            plan.update({"status": "incomplete", "reason_code": "next_response_has_no_text_atoms",
                         "recommended_route": "escalate"})
            stats["ack_spans_required"] += 1
            stats["ack_spans_incomplete"] += 1
        else:
            stats["ack_spans_required"] += 1
            for response_event, response_atom in response_atoms:
                job = _make_job(
                    run_id, profile_hash, profile,
                    "acknowledgment_response_pair", "acknowledgment_response",
                    user_event,
                    {"user_intent_excerpt": atom["text"],
                     "assistant_response_excerpt": response_atom["text"],
                     "user_timestamp": user_event.timestamp,
                     "response_timestamp": response_event.timestamp,
                     "ack_expectation": expectation},
                    user_span_id=span_id,
                    user_char_span=[atom["start"], atom["end"]],
                    response_event_id=response_event.event_id,
                    response_span_id=_span_id(response_event.event_id, response_atom),
                    response_char_span=[response_atom["start"], response_atom["end"]],
                    response_source_file_sha256=response_event.source.file_sha256,
                    response_source_line=response_event.source.line,
                    response_timestamp=response_event.timestamp,
                )
                jobs.append(job)
                plan["planned_job_ids"].append(job["job_id"])
            plan["planned_job_count"] = len(plan["planned_job_ids"])
            if not plan["planned_job_count"]:
                plan.update({"status": "incomplete", "reason_code": "acknowledgment_job_plan_empty",
                             "recommended_route": "escalate"})
                stats["ack_spans_incomplete"] += 1
            stats["ack_response_jobs"] += plan["planned_job_count"]
        plan["created_at"] = _now()
        plans.append(plan)
    return jobs, plans, stats


def _pin_state_and_phase2(run_id: str, profile_hash: str, profile: Mapping[str, Any],
                          streams: Mapping[str, Sequence[ReplayEvent]],
                          atoms_by_event: Mapping[str, Sequence[Mapping[str, Any]]],
                          user_jobs: Sequence[Dict[str, Any]],
                          user_results: Mapping[str, Mapping[str, Any]],
                          tokenizer: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Chronologically reduce intent/boundary outputs and plan phase-2 checks."""
    status_by_span, status_stats = _pin_statuses(user_jobs, user_results)
    boundary_status_by_span, boundary_stats = _assistant_boundary_statuses(
        user_jobs, user_results,
    )
    pair_groups, relation_stats = _relation_aggregates(user_jobs, user_results)
    pair_decisions: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for job in user_jobs:
        meta = job["meta"]
        if meta["gate"] == "user_message_relation":
            key = (meta["stream_id"], meta["prior_event_id"], meta["event_id"])
            pair_decisions[key].append({"prior_span_id": meta["prior_span_id"],
                                        "current_span_id": meta["current_span_id"],
                                        "job_id": job["job_id"],
                                        "result": user_results.get(job["job_id"])})

    event_by_id = {event.event_id: event for rows in streams.values() for event in rows}
    text_by_span: Dict[str, str] = {}
    for event_id, atoms in atoms_by_event.items():
        for atom in atoms:
            text_by_span[_span_id(event_id, atom)] = str(atom["text"])

    ordered_streams, unresolved = _stream_order(streams)
    active_by_span: Dict[str, Dict[str, Any]] = {}
    active_pin_ids_at_event: Dict[str, List[str]] = {}
    parent_pin_snapshots: Dict[str, List[str]] = {}
    parent_evidence_snapshots: Dict[str, List[Dict[str, Any]]] = {}
    stream_quality: Dict[str, Dict[str, Any]] = {}
    phase2_jobs: List[Dict[str, Any]] = []
    deterministic_rows: List[Dict[str, Any]] = []
    research_stats = {"research_boundaries": 0, "research_jobs": 0,
                      "research_incomplete_boundaries": 0}
    tool_stats = {"tool_calls": 0, "tool_pin_jobs": 0, "fixed_denies": 0,
                  "tool_unpinned": 0}
    compaction_stats = {"compact_boundaries": 0, "pin_id_checks": 0,
                        "semantic_unknown": 0}
    acknowledgment_stats = {"ack_spans_seen": 0, "ack_spans_required": 0,
                            "ack_spans_not_required": 0, "ack_spans_incomplete": 0,
                            "ack_spans_missing_response": 0, "ack_response_jobs": 0}
    plan_stats = {"assistant_plan_boundaries": 0, "plan_intent_jobs": 0,
                  "plan_boundary_incomplete": 0}

    for stream_id in ordered_streams:
        rows = list(streams[stream_id])
        sidechain = any(event.is_sidechain for event in rows)
        delegated = next((event for event in rows
                          if event.is_sidechain and event.kind == "delegated_prompt"), None)
        link_status = delegated.metadata.get("delegation_link_status") if delegated else None
        parent_event_id = delegated.metadata.get("delegated_from_event_id") if delegated else None
        parent_stream_id = delegated.metadata.get("delegated_from_stream_id") if delegated else None
        complete = True
        quality_reasons: set[str] = set()
        active: List[str] = []
        inherited: List[str] = []
        inherited_evidence: List[Dict[str, Any]] = []
        if sidechain:
            if stream_id in unresolved or link_status != "resolved":
                complete = False
                quality_reasons.add("unresolved_sidechain_parent")
            elif parent_event_id not in parent_pin_snapshots or parent_stream_id not in streams:
                complete = False
                quality_reasons.add("missing_parent_snapshot")
            else:
                inherited = list(parent_pin_snapshots[str(parent_event_id)])
                active = list(inherited)
                inherited_evidence = list(parent_evidence_snapshots.get(str(parent_event_id), []))
                if not inherited_evidence:
                    # An empty parent evidence set is valid only if its snapshot
                    # was recorded explicitly at the delegation call.
                    if str(parent_event_id) not in parent_evidence_snapshots:
                        complete = False
                        quality_reasons.add("missing_parent_evidence_snapshot")
        stream_quality[stream_id] = {"complete": complete,
                                      "sidechain": sidechain,
                                      "delegation_status": link_status or ("unresolved" if stream_id in unresolved else None),
                                      "parent_event_id": parent_event_id,
                                      "reason_codes": sorted(quality_reasons)}

        def mark_incomplete(reason: str) -> None:
            nonlocal complete
            complete = False
            quality_reasons.add(reason)
            stream_quality[stream_id]["complete"] = False
            stream_quality[stream_id]["reason_codes"] = sorted(quality_reasons)

        human_history: List[ReplayEvent] = []
        observed_prefix: List[ReplayEvent] = []
        for event in rows:
            active_pin_ids_at_event[event.event_id] = list(active)
            if event.kind == "human_user" and event.authority == "human":
                for previous in human_history:
                    key = (stream_id, previous.event_id, event.event_id)
                    decisions = pair_decisions.get(key, [])
                    expected_chunks = (len(atoms_by_event[previous.event_id])
                                       * len(atoms_by_event[event.event_id]))
                    if len(decisions) != expected_chunks:
                        mark_incomplete("user_pair_job_plan_gap")
                    relations = []
                    tasks = []
                    relation_details = []
                    for item in sorted(decisions, key=lambda x: (x["prior_span_id"], x["current_span_id"])):
                        result = item.get("result") or {}
                        if result.get("status") == "scored" and result.get("answers"):
                            answer = result["answers"]
                            relation = answer["relation"]["choice"]
                            task_context = answer["task_context"]["choice"]
                            relations.append(relation)
                            tasks.append(task_context)
                        else:
                            relation, task_context = "unclear", "unclear"
                            mark_incomplete("user_pair_result_missing")
                        if relation in {"unclear", "reopens_or_uncertain"}:
                            mark_incomplete("user_pair_relation_uncertain")
                        if task_context == "unclear":
                            mark_incomplete("task_context_uncertain")
                        relation_details.append({"prior_span_id": item["prior_span_id"],
                                                 "current_span_id": item["current_span_id"],
                                                 "relation": relation,
                                                 "task_context": task_context,
                                                 "job_id": item["job_id"]})
                    pair_relation = relations[0] if relations and all(x == relations[0] for x in relations) else "mixed"
                    pair_task = tasks[0] if tasks and all(x == tasks[0] for x in tasks) else "mixed"
                    if pair_relation == "mixed":
                        mark_incomplete("user_pair_relations_disagree")
                    if pair_task == "mixed":
                        mark_incomplete("task_context_relations_disagree")
                    deterministic_rows.append({
                        "schema_version": 1, "record_type": "message_pair_aggregate",
                        "run_id": run_id, "profile_sha256": profile_hash,
                        "stream_sha256": _hash_id(stream_id),
                        "prior_event_id": previous.event_id, "event_id": event.event_id,
                        "relation": pair_relation, "task_context": pair_task,
                        "expected_chunk_pairs": len(decisions),
                        "scored_chunk_pairs": sum(item["relation"] != "unclear"
                                                   for item in relation_details),
                        "chunk_relations": relation_details,
                        "created_at": _now(),
                    })
                    span_relations: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
                    for item in relation_details:
                        span_relations[(item["prior_span_id"], item["current_span_id"])].append(item)
                    for (prior_span_id, current_span_id), items in sorted(span_relations.items()):
                        labels = {item["relation"] for item in items}
                        if len(labels) != 1:
                            mark_incomplete("span_relation_outputs_disagree")
                            continue
                        if labels != {"revises_or_supersedes"}:
                            continue
                        current_pin = status_by_span.get(current_span_id, {})
                        prior_pin = active_by_span.get(prior_span_id)
                        if (prior_pin is not None and prior_pin.get("active")
                                and current_pin.get("status") in {"durable_assertion", "tentative_or_reconsidering"}
                                and prior_pin.get("status") in {"durable_assertion", "tentative_or_reconsidering"}):
                            prior_pin["active"] = False
                            prior_pin["superseded_by"] = current_span_id
                            deterministic_rows.append({
                                "schema_version": 1, "record_type": "supersession_edge",
                                "run_id": run_id, "profile_sha256": profile_hash,
                                "stream_sha256": _hash_id(stream_id),
                                "prior_pin_id": prior_span_id,
                                "current_pin_id": current_span_id,
                                "prior_event_id": previous.event_id,
                                "event_id": event.event_id,
                                "relation_job_ids": [item["job_id"] for item in items], "status": "applied",
                                "created_at": _now(),
                            })
                for atom in atoms_by_event[event.event_id]:
                    pin_id = _span_id(event.event_id, atom)
                    pin_status = status_by_span.get(pin_id)
                    status = pin_status["status"] if pin_status else "unclear"
                    if not pin_status or not pin_status.get("scored") or status == "unclear":
                        mark_incomplete("user_pin_status_uncertain_or_missing")
                    active_candidate = status in {
                        "durable_assertion", "tentative_or_reconsidering", "unclear",
                    }
                    pin = {
                        "pin_id": pin_id, "source_event_id": event.event_id,
                        "stream_id": stream_id, "status": status,
                        "active": active_candidate, "char_span": [atom["start"], atom["end"]],
                        "timestamp": event.timestamp,
                        "text": atom["text"], "source_file_sha256": event.source.file_sha256,
                        "source_line": event.source.line,
                    }
                    active_by_span[pin_id] = pin
                    if active_candidate:
                        active.append(pin_id)
                ack_jobs, ack_plans, ack_counts = _acknowledgment_jobs(
                    run_id, profile_hash, profile, event, rows,
                    atoms_by_event[event.event_id], status_by_span, tokenizer,
                )
                phase2_jobs.extend(ack_jobs)
                deterministic_rows.extend(ack_plans)
                for key, value in ack_counts.items():
                    acknowledgment_stats[key] += value
                human_history.append(event)
            elif event.kind == "assistant_text" and event.authority == "agent":
                for atom in atoms_by_event.get(event.event_id, []):
                    span_id = _span_id(event.event_id, atom)
                    boundary = boundary_status_by_span.get(span_id)
                    boundary_status = (str(boundary.get("status", "unclear"))
                                       if boundary else "unclear")
                    boundary_scored = bool(boundary and boundary.get("scored"))
                    boundary_row = {
                        "schema_version": 1, "record_type": "assistant_boundary_aggregate",
                        "run_id": run_id, "profile_sha256": profile_hash,
                        "stream_sha256": _hash_id(stream_id),
                        "event_id": event.event_id, "span_id": span_id,
                        "source_file_sha256": event.source.file_sha256,
                        "source_line": event.source.line,
                        "source_timestamp": event.timestamp,
                        "status": boundary_status if boundary_scored else "incomplete",
                        "recommended_route": None if boundary_scored and boundary_status != "unclear" else "escalate",
                        "reason_code": ("assistant_boundary_unclear"
                                        if not boundary_scored or boundary_status == "unclear"
                                        else "boundary_classified"),
                        "decision_job_id": boundary.get("job_id") if boundary else None,
                        "decision_receipt_time": _now(),
                    }
                    deterministic_rows.append(boundary_row)
                    if not boundary_scored or boundary_status == "unclear":
                        plan_stats["plan_boundary_incomplete"] += 1
                        continue
                    if boundary_status == "other":
                        continue
                    is_plan = boundary_status in {"proposed_plan", "plan_and_claim"}
                    is_claim = boundary_status in {"factual_claim", "plan_and_claim"}
                    if is_plan:
                        plan_stats["assistant_plan_boundaries"] += 1
                        active_ids = [pin_id for pin_id in active
                                      if active_by_span.get(pin_id, {}).get("active")]
                        planned_ids: List[str] = []
                        for pin_id in active_ids:
                            pin = active_by_span[pin_id]
                            job = _make_job(
                                run_id, profile_hash, profile, "plan_intent_pair",
                                "plan_pin_relation", event,
                                {"proposed_plan_excerpt": atom["text"],
                                 "active_user_pin_excerpt": pin["text"],
                                 "plan_timestamp": event.timestamp,
                                 "intent_timestamp": pin["timestamp"],
                                 "pin_status": pin["status"]},
                                plan_span_id=span_id,
                                plan_char_span=[atom["start"], atom["end"]],
                                pin_id=pin_id, pin_source_event_id=pin["source_event_id"],
                                pin_char_span=pin["char_span"],
                                pin_source_file_sha256=pin["source_file_sha256"],
                                pin_source_line=pin["source_line"],
                            )
                            planned_ids.append(job["job_id"])
                            phase2_jobs.append(job)
                        plan_stats["plan_intent_jobs"] += len(planned_ids)
                        plan_complete = bool(stream_quality.get(stream_id, {}).get("complete", True))
                        deterministic_rows.append({
                            "schema_version": 1, "record_type": "plan_gate_plan",
                            "run_id": run_id, "profile_sha256": profile_hash,
                            "stream_sha256": _hash_id(stream_id),
                            "event_id": event.event_id, "plan_span_id": span_id,
                            "plan_char_span": [atom["start"], atom["end"]],
                            "source_file_sha256": event.source.file_sha256,
                            "source_line": event.source.line,
                            "source_timestamp": event.timestamp,
                            "boundary_status": boundary_status,
                            "expected_pin_ids": active_ids,
                            "planned_job_count": len(planned_ids),
                            "planned_job_ids": planned_ids,
                            "status": "planned" if plan_complete else "incomplete",
                            "recommended_route": None if plan_complete else "escalate",
                            "created_at": _now(),
                        })
                    if is_claim:
                        research_stats["research_boundaries"] += 1
                        research_jobs, complete_pack, pack_meta = _research_jobs(
                            run_id, profile_hash, profile, event, rows, observed_prefix,
                            tokenizer, max_tokens=int(profile["inference"]["state_chunk_tokens"]),
                            overlap_tokens=int(profile["inference"]["state_chunk_overlap_tokens"]),
                            inherited_evidence=inherited_evidence,
                            claim_atoms_override=[(event, atom)],
                        )
                        phase2_jobs.extend(research_jobs)
                        research_stats["research_jobs"] += len(research_jobs)
                        if not complete_pack:
                            research_stats["research_incomplete_boundaries"] += 1
                        deterministic_rows.append(_research_plan_receipt(
                            run_id, profile_hash, event, pack_meta, complete_pack,
                            len(research_jobs),
                        ))
            elif event.kind == "tool_call":
                tool_stats["tool_calls"] += 1
                fixed_deny = hard_deny_reason(event)
                if str(event.metadata.get("tool_name", "")).lower() == "agent":
                    parent_pin_snapshots[event.event_id] = [pin_id for pin_id in active
                                                            if active_by_span.get(pin_id, {}).get("active")]
                    parent_evidence_snapshots[event.event_id] = _extract_evidence(
                        observed_prefix, stream_id,
                    )
                if _is_coding_boundary(event) and not fixed_deny:
                    research_stats["research_boundaries"] += 1
                    claim_atoms = _classified_claim_atoms(
                        observed_prefix, atoms_by_event, boundary_status_by_span,
                    )
                    research_jobs, complete_pack, pack_meta = _research_jobs(
                        run_id, profile_hash, profile, event, rows, observed_prefix,
                        tokenizer, max_tokens=int(profile["inference"]["state_chunk_tokens"]),
                        overlap_tokens=int(profile["inference"]["state_chunk_overlap_tokens"]),
                        inherited_evidence=inherited_evidence,
                        claim_atoms_override=claim_atoms,
                    )
                    phase2_jobs.extend(research_jobs)
                    research_stats["research_jobs"] += len(research_jobs)
                    if not complete_pack:
                        research_stats["research_incomplete_boundaries"] += 1
                    deterministic_rows.append(_research_plan_receipt(
                        run_id, profile_hash, event, pack_meta, complete_pack,
                        len(research_jobs),
                    ))
                active_ids = [pin_id for pin_id in active
                              if active_by_span.get(pin_id, {}).get("active")]
                if fixed_deny:
                    tool_stats["fixed_denies"] += 1
                    deterministic_rows.append({
                        "schema_version": 1, "record_type": "tool_gate_aggregate",
                        "run_id": run_id, "profile_sha256": profile_hash,
                        "stream_sha256": _hash_id(stream_id), "event_id": event.event_id,
                        "source_file_sha256": event.source.file_sha256,
                        "source_line": event.source.line, "source_timestamp": event.timestamp,
                        "status": "scored", "verdict": "deny",
                        "recommended_route": "escalate",
                        "reason_code": fixed_deny,
                        "fixed_deny_rule": fixed_deny, "expected_pin_ids": active_ids,
                        "planned_pair_jobs": 0, "decision_receipt_time": _now(),
                        "created_at": _now(),
                    })
                elif not active_ids:
                    tool_stats["tool_unpinned"] += 1
                    deterministic_rows.append({
                        "schema_version": 1, "record_type": "tool_gate_aggregate",
                        "run_id": run_id, "profile_sha256": profile_hash,
                        "stream_sha256": _hash_id(stream_id), "event_id": event.event_id,
                        "source_file_sha256": event.source.file_sha256,
                        "source_line": event.source.line, "source_timestamp": event.timestamp,
                        "status": "scored" if complete else "incomplete",
                        "verdict": "allow" if complete else "escalate",
                        "recommended_route": "proceed" if complete else "escalate",
                        "reason_code": "no_active_intent_constraint" if complete else "stream_coverage_incomplete",
                        "fixed_deny_rule": None, "expected_pin_ids": [],
                        "planned_pair_jobs": 0, "decision_receipt_time": _now(),
                        "created_at": _now(),
                    })
                else:
                    tool_atoms = _atomize(
                        event.text, tokenizer, int(profile["inference"]["state_chunk_tokens"]),
                        int(profile["inference"]["state_chunk_overlap_tokens"]))
                    planned: List[str] = []
                    for pin_id in active_ids:
                        pin = active_by_span[pin_id]
                        for atom in tool_atoms:
                            job = _make_job(
                                run_id, profile_hash, profile, "tool_pin_pair", "tool_pin_relation",
                                event,
                                 {"proposed_tool_excerpt": atom["text"],
                                 "active_user_pin_excerpt": pin["text"],
                                 "pin_status": pin["status"]},
                                pin_id=pin_id, pin_source_event_id=pin["source_event_id"],
                                tool_span=[atom["start"], atom["end"]],
                                pin_char_span=pin["char_span"],
                                pin_source_file_sha256=pin["source_file_sha256"],
                                pin_source_line=pin["source_line"],
                            )
                            planned.append(job["job_id"])
                            phase2_jobs.append(job)
                    tool_stats["tool_pin_jobs"] += len(planned)
                    deterministic_rows.append({
                        "schema_version": 1, "record_type": "tool_gate_plan",
                        "run_id": run_id, "profile_sha256": profile_hash,
                        "stream_sha256": _hash_id(stream_id), "event_id": event.event_id,
                        "expected_pin_ids": active_ids,
                        "tool_chunk_count": len(tool_atoms),
                        "planned_pair_jobs": len(planned), "planned_job_ids": planned,
                        "stream_complete_before_event": complete,
                        "created_at": _now(),
                    })
                if str(event.metadata.get("tool_name", "")).lower() == "agent":
                    # Snapshot must be frozen at this exact delegation call.
                    parent_pin_snapshots[event.event_id] = [pin_id for pin_id in active
                                                            if active_by_span.get(pin_id, {}).get("active")]
                if fixed_deny:
                    pass
            elif event.kind == "compact_boundary":
                compaction_stats["compact_boundaries"] += 1
                checks = []
                for pin_id in active:
                    pin = active_by_span.get(pin_id)
                    if not pin or not pin.get("active"):
                        continue
                    retention = compact_retention(event, pin["source_event_id"])
                    checks.append({"pin_id": pin_id,
                                   "source_event_id": pin["source_event_id"],
                                   "source_id_status": retention.get("source_id_status"),
                                   "semantic_status": "unknown"})
                compaction_stats["pin_id_checks"] += len(checks)
                compaction_stats["semantic_unknown"] += len(checks)
                deterministic_rows.append({
                    "schema_version": 1, "record_type": "compaction_gate",
                    "run_id": run_id, "profile_sha256": profile_hash,
                    "stream_sha256": _hash_id(stream_id), "event_id": event.event_id,
                    "status": "scored" if complete else "incomplete",
                    "pin_id_checks": checks,
                    "semantic_status": "unknown_source_contains_ids_only",
                    "model_decision": "not_assessed_no_captured_before_after_prose",
                    "created_at": _now(),
                })
            observed_prefix.append(event)
            if event.kind == "tool_call" and str(event.metadata.get("tool_name", "")).lower() == "agent":
                parent_evidence_snapshots[event.event_id] = _extract_evidence(observed_prefix[:-1], stream_id)
            if event.kind == "tool_call":
                active_pin_ids_at_event[event.event_id] = [pin_id for pin_id in active
                                                           if active_by_span.get(pin_id, {}).get("active")]

    phase2_plan_stats = {
        **research_stats, **tool_stats, **compaction_stats,
        **acknowledgment_stats, **plan_stats,
        "phase2_jobs": len(phase2_jobs),
        "unresolved_sidechain_streams": len(unresolved),
        "stream_count": len(streams),
        "stream_quality": {key: {k: v for k, v in value.items() if k != "parent_event_id"}
                           for key, value in stream_quality.items()},
    }
    return phase2_jobs, deterministic_rows, {
        "pin_status": status_stats,
        "assistant_boundaries": boundary_stats,
        "relations": relation_stats,
        "phase2": phase2_plan_stats,
        "active_pins": active_by_span,
        "active_pin_ids_at_event": active_pin_ids_at_event,
        "pair_groups": pair_groups,
        "parent_pin_snapshots": parent_pin_snapshots,
    }


def _is_coding_boundary(event: ReplayEvent) -> bool:
    """The profile freezes these file-changing tool kinds as action boundaries."""
    return event.kind == "tool_call" and str(event.metadata.get("tool_name", "")).lower() in {
        "edit", "multiedit", "write", "create", "notebookedit", "apply_patch",
    }


def _extract_evidence(prefix: Sequence[ReplayEvent], stream_id: str) -> List[Dict[str, Any]]:
    """Copy only evidence visible in this stream prefix; text remains private."""
    calls: Dict[str, ReplayEvent] = {}
    evidence: List[Dict[str, Any]] = []
    for event in sorted(prefix, key=lambda item: (item.sequence, item.event_id)):
        if event.stream_id != stream_id:
            raise AdapterError("cross_stream_research_evidence")
        if event.kind == "tool_call" and event.tool_use_id:
            calls[event.tool_use_id] = event
            if str(event.metadata.get("tool_name", "unknown")).lower() in _RESEARCH_TOOLS:
                evidence.append({"event_id": event.event_id, "kind": "source_request",
                                 "source_event_id": event.event_id,
                                 "text": event.text,
                                 "source_file_sha256": event.source.file_sha256,
                                 "source_line": event.source.line,
                                 "timestamp": event.timestamp,
                                 "sequence": event.sequence})
            continue
        if event.kind == "tool_result":
            call = calls.get(event.tool_use_id)
            if call is None or str(call.metadata.get("tool_name", "unknown")).lower() not in _RESEARCH_TOOLS:
                continue
            kind, source_event_id = "retrieved_source", call.event_id
        elif event.kind == "assistant_text" and event.authority == "agent":
            kind, source_event_id = "agent_claim", event.event_id
        else:
            continue
        evidence.append({"event_id": event.event_id, "kind": kind,
                         "source_event_id": source_event_id,
                         "text": event.text,
                         "source_file_sha256": event.source.file_sha256,
                         "source_line": event.source.line,
                         "timestamp": event.timestamp,
                         "sequence": event.sequence})
    return evidence


def _research_claims(event: ReplayEvent,
                     prefix: Sequence[ReplayEvent]) -> List[ReplayEvent]:
    """Return a compact, source-addressable claim set visible at this boundary."""
    prompts = [item for item in prefix if item.kind in {"human_user", "delegated_prompt"}]
    anchor = prompts[-1] if prompts else None
    claims = [item for item in prefix
              if item.kind == "assistant_text" and item.authority == "agent"
              and (not prompts or item.sequence > prompts[-1].sequence)]
    selected = [item for item in (anchor, claims[-1] if claims else None, event) if item]
    seen: set[str] = set()
    unique = []
    for item in selected:
        if item.event_id not in seen:
            unique.append(item)
            seen.add(item.event_id)
    return unique


def _classified_claim_atoms(prefix: Sequence[ReplayEvent],
                            atoms_by_event: Mapping[str, Sequence[Mapping[str, Any]]],
                            boundary_status_by_span: Mapping[str, Mapping[str, Any]]
                            ) -> List[Tuple[ReplayEvent, Mapping[str, Any]]]:
    """Return only assistant spans Laya marked as verifiable factual claims."""
    prompts = [item for item in prefix
               if item.kind in {"human_user", "delegated_prompt"}
               and item.authority in {"human", "agent"}]
    latest_prompt_sequence = prompts[-1].sequence if prompts else -1
    claims: List[Tuple[ReplayEvent, Mapping[str, Any]]] = []
    for item in prefix:
        if (item.kind != "assistant_text" or item.authority != "agent"
                or item.sequence <= latest_prompt_sequence):
            continue
        for atom in atoms_by_event.get(item.event_id, []):
            boundary = boundary_status_by_span.get(_span_id(item.event_id, atom), {})
            if boundary.get("status") in {"factual_claim", "plan_and_claim"}:
                claims.append((item, atom))
    return claims


def _lexical_terms(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9_./-]{2,}", text.lower())
            if word not in _STOPWORDS and not word.isdigit()}


def _research_jobs(run_id: str, profile_hash: str, profile: Mapping[str, Any],
                   event: ReplayEvent, rows: Sequence[ReplayEvent], prefix: Sequence[ReplayEvent],
                   tokenizer: Any, *, max_tokens: int, overlap_tokens: int = 32,
                   inherited_evidence: Sequence[Mapping[str, Any]] = (),
                   claim_atoms_override: Optional[Sequence[Tuple[ReplayEvent, Mapping[str, Any]]]] = None
                   ) -> Tuple[List[Dict[str, Any]], bool, Dict[str, Any]]:
    evidence_records = list(inherited_evidence) + _extract_evidence(prefix, event.stream_id)
    # Requests and agent assertions remain provenance records, but only returned
    # source content can count as evidence for a claim.
    evidence = [item for item in evidence_records
                if item.get("kind") == "retrieved_source"]
    excluded_non_evidence = [item for item in evidence_records
                             if item.get("kind") != "retrieved_source"]
    if claim_atoms_override is None:
        claim_events = _research_claims(event, prefix)
        claim_atoms = [(claim_event, atom)
                       for claim_event in claim_events
                       for atom in _atomize(claim_event.text, tokenizer, max_tokens, overlap_tokens)]
    else:
        claim_atoms = list(claim_atoms_override)
        claim_events = list({claim_event.event_id: claim_event
                             for claim_event, _atom in claim_atoms}.values())
    query = "\n".join(str(atom["text"]) for _claim_event, atom in claim_atoms)
    terms = _lexical_terms(query)
    ranked: List[Tuple[int, int, str, Dict[str, Any]]] = []
    for index, item in enumerate(evidence):
        if not item.get("text"):
            continue
        overlap = len(terms & _lexical_terms(str(item["text"])))
        if overlap:
            ranked.append((overlap, int(item.get("sequence", -1)), str(item["event_id"]), dict(item)))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    evidence_atoms: List[Tuple[Dict[str, Any], Dict[str, Any], int]] = []
    for score, _sequence, _event_id, item in ranked:
        for atom in _atomize(str(item["text"]), tokenizer, max_tokens, overlap_tokens):
            if _lexical_terms(atom["text"]) & terms:
                evidence_atoms.append((item, atom, score))

    claim_coverage = []
    for claim_event, claim_atom in claim_atoms:
        claim_terms = _lexical_terms(str(claim_atom["text"]))
        candidate_ids = sorted({
            evidence_item["event_id"]
            for evidence_item, evidence_atom, _score in evidence_atoms
            if claim_terms & _lexical_terms(str(evidence_atom["text"]))
        })
        claim_coverage.append({
            "claim_source_event_id": claim_event.event_id,
            "claim_source_file_sha256": claim_event.source.file_sha256,
            "claim_source_line": claim_event.source.line,
            "claim_timestamp": claim_event.timestamp,
            "claim_span": [claim_atom["start"], claim_atom["end"]],
            "candidate_evidence_event_ids": candidate_ids,
            "candidate_evidence_count": len(candidate_ids),
        })
    unmatched_claim_spans = [item for item in claim_coverage
                             if item["candidate_evidence_count"] == 0]
    hard_cap = int(profile["inference"].get("max_research_pairs_per_boundary", 256))
    planned_pair_count = len(claim_atoms) * len(evidence_atoms)
    selected_pairs: List[Tuple[ReplayEvent, Dict[str, Any], Dict[str, Any],
                               Dict[str, Any], int]] = []
    for claim_event, claim_atom in claim_atoms:
        for evidence_item, evidence_atom, score in evidence_atoms:
            if len(selected_pairs) >= hard_cap:
                break
            selected_pairs.append((claim_event, claim_atom, evidence_item, evidence_atom, score))
        if len(selected_pairs) >= hard_cap:
            break
    complete = len(selected_pairs) == planned_pair_count
    omitted_evidence_ids: List[str] = []
    if not complete and evidence_atoms:
        next_claim_index, next_evidence_index = divmod(len(selected_pairs), len(evidence_atoms))
        omitted = {item[0]["event_id"] for item in evidence_atoms[next_evidence_index:]}
        if next_claim_index + 1 < len(claim_atoms):
            omitted.update(item[0]["event_id"] for item in evidence_atoms)
        omitted_evidence_ids = sorted(omitted)
    jobs: List[Dict[str, Any]] = []
    for claim_event, claim_atom, evidence_item, evidence_atom, _score in selected_pairs:
        jobs.append(_make_job(
            run_id, profile_hash, profile, "research_evidence_pair", "research_evidence_relation",
            event,
            {"claim_excerpt": claim_atom["text"],
             "as_of_evidence_excerpt": evidence_atom["text"],
             "evidence_kind": evidence_item["kind"],
             "claim_timestamp": claim_event.timestamp},
            claim_span=[claim_atom["start"], claim_atom["end"]],
            claim_source_event_id=claim_event.event_id,
            claim_source_file_sha256=claim_event.source.file_sha256,
            claim_source_line=claim_event.source.line,
            claim_timestamp=claim_event.timestamp,
            evidence_event_id=evidence_item["event_id"],
            evidence_span=[evidence_atom["start"], evidence_atom["end"]],
            evidence_source_file_sha256=evidence_item.get("source_file_sha256"),
            evidence_source_line=evidence_item.get("source_line"),
            evidence_source_event_id=evidence_item.get("source_event_id"),
            evidence_timestamp=evidence_item.get("timestamp"),
        ))
    pack_meta = {
        "query_sha256": _sha(query.encode("utf-8")),
        "retrieval_method": "lexical_overlap_v1",
        "eligible_evidence_records": len(evidence),
        "excluded_non_evidence_records": len(excluded_non_evidence),
        "excluded_non_evidence_event_ids": [
            {"event_id": item.get("event_id"), "kind": item.get("kind")}
            for item in excluded_non_evidence
        ],
        "matching_evidence_records": len(ranked),
        "matching_evidence_atoms": len(evidence_atoms),
        "claim_events": [item.event_id for item in claim_events],
        "claim_atoms": len(claim_atoms),
        "claim_coverage": claim_coverage,
        "unmatched_claim_spans": unmatched_claim_spans,
        "planned_pairs": planned_pair_count,
        "scheduled_pairs": len(jobs),
        "omitted_pairs": max(0, planned_pair_count - len(jobs)),
        "included_evidence_event_ids": list(dict.fromkeys(item[2]["event_id"] for item in selected_pairs)),
        "omitted_evidence_event_ids": omitted_evidence_ids,
    }
    return jobs, complete, pack_meta


def _research_plan_receipt(run_id: str, profile_hash: str, event: ReplayEvent,
                           pack_meta: Mapping[str, Any], complete: bool,
                           job_count: int) -> Dict[str, Any]:
    return {
        "schema_version": 1, "record_type": "research_gate_plan",
        "run_id": run_id, "profile_sha256": profile_hash,
        "event_id": event.event_id, "stream_sha256": _hash_id(event.stream_id),
        "source_file_sha256": event.source.file_sha256,
        "source_line": event.source.line, "source_timestamp": event.timestamp,
        "status": "planned" if complete else "incomplete_context_budget",
        "pack": dict(pack_meta), "planned_job_count": job_count,
        "created_at": _now(),
    }


def _aggregate_phase2(phase2_jobs: Sequence[Dict[str, Any]],
                      phase2_results: Mapping[str, Mapping[str, Any]],
                      deterministic_rows: Sequence[Mapping[str, Any]],
                      active_pins: Mapping[str, Mapping[str, Any]],
                      stream_quality: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve acknowledgment, research, and tool outcomes deterministically."""
    outputs = [dict(row) for row in deterministic_rows]
    by_tool: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    by_research: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    by_ack: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    by_plan: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    research_plans: Dict[Tuple[str, str], Mapping[str, Any]] = {}
    acknowledgment_plans: Dict[Tuple[str, str], Mapping[str, Any]] = {}
    plan_plans: Dict[Tuple[str, str], Mapping[str, Any]] = {}
    for row in deterministic_rows:
        if row.get("record_type") == "research_gate_plan":
            research_plans[(str(row.get("stream_sha256", "")), str(row.get("event_id", "")))] = row
        elif row.get("record_type") == "acknowledgment_gate_plan":
            acknowledgment_plans[(str(row.get("event_id", "")),
                                  str(row.get("span_id", "")))] = row
        elif row.get("record_type") == "plan_gate_plan":
            plan_plans[(str(row.get("event_id", "")),
                        str(row.get("plan_span_id", "")))] = row
    for job in phase2_jobs:
        meta = job["meta"]
        result = phase2_results.get(job["job_id"])
        row = {"job_id": job["job_id"], "meta": meta, "result": result}
        if meta["gate"] == "tool_pin_relation":
            by_tool[(meta["stream_id"], meta["event_id"])].append(row)
        elif meta["gate"] == "research_evidence_relation":
            by_research[(meta["stream_id"], meta["event_id"])].append(row)
        elif meta["gate"] == "acknowledgment_response":
            by_ack[(str(meta["event_id"]), str(meta["user_span_id"]))].append(row)
        elif meta["gate"] == "plan_pin_relation":
            by_plan[(str(meta["event_id"]), str(meta["plan_span_id"]))].append(row)

    acknowledgment_by_event: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for key, plan in sorted(acknowledgment_plans.items()):
        jobs = sorted(by_ack.get(key, []), key=lambda item: (
            str(item["meta"].get("response_event_id", "")),
            str(item["meta"].get("response_span_id", "")),
        ))
        plan_status = str(plan.get("status", "incomplete"))
        choices: List[str] = []
        details = []
        missing = (plan_status == "planned"
                   and len(jobs) != int(plan.get("planned_job_count", 0)))
        for item in jobs:
            result = item["result"] or {}
            if result.get("status") != "scored" or not result.get("answers"):
                missing = True
                choice = "unclear"
            else:
                choice = result["answers"]["acknowledgment_response"]["choice"]
            choices.append(choice)
            details.append({
                "job_id": item["job_id"],
                "response_event_id": item["meta"].get("response_event_id"),
                "response_span_id": item["meta"].get("response_span_id"),
                "response_timestamp": item["meta"].get("response_timestamp"),
                "response_source_file_sha256": item["meta"].get("response_source_file_sha256"),
                "response_source_line": item["meta"].get("response_source_line"),
                "response_char_span": item["meta"].get("response_char_span"),
                "choice": choice,
                "status": (item["result"] or {}).get("status", "missing"),
            })
        if plan_status == "not_required":
            outcome, route = "not_required", None
            reason = "acknowledgment_not_required"
        elif plan_status == "omitted":
            outcome, route = "omitted", "reconfirm_intent"
            reason = str(plan.get("reason_code", "acknowledgment_omitted"))
        elif plan_status != "planned" or missing or not jobs:
            outcome, route = "incomplete", "escalate"
            reason = str(plan.get("reason_code", "acknowledgment_coverage_incomplete"))
        elif "unclear" in choices:
            outcome, route = "incomplete", "escalate"
            reason = "acknowledgment_model_uncertain"
        elif "contradicted" in choices and "accurate" in choices:
            outcome, route = "mixed", "reconfirm_intent"
            reason = "acknowledgment_chunks_disagree"
        elif "contradicted" in choices:
            outcome, route = "contradicted", "reconfirm_intent"
            reason = "acknowledgment_contradicts_intent"
        elif "accurate" in choices:
            outcome, route = "accurate", "proceed"
            reason = "next_response_carries_intent"
        elif "partial" in choices:
            outcome, route = "partial", "reconfirm_intent"
            reason = "next_response_omits_or_weakens_constraint"
        elif choices and all(choice == "omitted" for choice in choices):
            outcome, route = "omitted", "reconfirm_intent"
            reason = "next_response_does_not_reflect_intent"
        else:
            outcome, route = "incomplete", "escalate"
            reason = "acknowledgment_decision_unresolved"
        aggregate = {
            "schema_version": 1, "record_type": "acknowledgment_gate_aggregate",
            "run_id": plan.get("run_id"), "event_id": plan.get("event_id"),
            "stream_sha256": plan.get("stream_sha256"),
            "span_id": plan.get("span_id"),
            "source_file_sha256": plan.get("source_file_sha256"),
            "source_line": plan.get("source_line"),
            "source_timestamp": plan.get("source_timestamp"),
            "response_event_ids": plan.get("response_event_ids", []),
            "ack_required": plan.get("ack_required"),
            "status": outcome, "recommended_route": route, "reason_code": reason,
            "expected_job_count": int(plan.get("planned_job_count", 0)),
            "scored_job_count": sum(item["status"] == "scored" for item in details),
            "decision_details": details,
            "decision_receipt_time": _now(),
        }
        outputs.append(aggregate)
        acknowledgment_by_event[str(plan.get("event_id", ""))].append(aggregate)

    for event_id, spans in sorted(acknowledgment_by_event.items()):
        assessed = [row for row in spans if row["status"] != "not_required"]
        if not assessed:
            status, route, reason = "not_required", None, "no_acknowledgment_candidate"
        elif any(row["status"] == "incomplete" for row in assessed):
            status, route, reason = "incomplete", "escalate", "acknowledgment_coverage_incomplete"
        elif any(row["recommended_route"] == "reconfirm_intent" for row in assessed):
            status, route, reason = "needs_reconfirmation", "reconfirm_intent", "next_response_missed_or_conflicted"
        else:
            status, route, reason = "accurate", "proceed", "next_response_carries_all_checked_spans"
        outputs.append({
            "schema_version": 1, "record_type": "acknowledgment_message_aggregate",
            "event_id": event_id,
            "stream_sha256": spans[0].get("stream_sha256") if spans else None,
            "source_timestamp": spans[0].get("source_timestamp") if spans else None,
            "span_ids": [row.get("span_id") for row in spans],
            "status": status, "recommended_route": route, "reason_code": reason,
            "required_or_uncertain_span_count": len(assessed),
            "planned_job_count": sum(int(row.get("expected_job_count", 0)) for row in assessed),
            "scored_job_count": sum(int(row.get("scored_job_count", 0)) for row in assessed),
            "decision_receipt_time": _now(),
        })

    for key, plan in sorted(plan_plans.items()):
        jobs = sorted(by_plan.get(key, []), key=lambda item: str(item["meta"].get("pin_id", "")))
        missing = (plan.get("status") != "planned"
                   or len(jobs) != int(plan.get("planned_job_count", 0)))
        if jobs and not stream_quality.get(str(jobs[0]["meta"]["stream_id"]), {}).get("complete", True):
            missing = True
        choices: List[str] = []
        details = []
        for item in jobs:
            result = item["result"] or {}
            if result.get("status") != "scored" or not result.get("answers"):
                missing = True
                choice = "uncertain"
            else:
                choice = result["answers"]["plan_intent"]["choice"]
            choices.append(choice)
            details.append({
                "job_id": item["job_id"],
                "pin_id": item["meta"].get("pin_id"),
                "pin_source_event_id": item["meta"].get("pin_source_event_id"),
                "choice": choice,
                "status": (item["result"] or {}).get("status", "missing"),
            })
        if "conflict" in choices:
            outcome, route, reason = "conflict", "rethink_plan", "proposed_plan_conflicts_with_user_intent"
        elif missing or "uncertain" in choices:
            outcome, route, reason = "incomplete", "escalate", "plan_intent_coverage_incomplete"
        else:
            outcome, route, reason = "consistent", "proceed", "proposed_plan_is_not_in_conflict"
        outputs.append({
            "schema_version": 1, "record_type": "plan_gate_aggregate",
            "run_id": plan.get("run_id"), "event_id": plan.get("event_id"),
            "stream_sha256": plan.get("stream_sha256"),
            "plan_span_id": plan.get("plan_span_id"),
            "plan_char_span": plan.get("plan_char_span"),
            "source_file_sha256": plan.get("source_file_sha256"),
            "source_line": plan.get("source_line"),
            "source_timestamp": plan.get("source_timestamp"),
            "boundary_status": plan.get("boundary_status"),
            "expected_pin_ids": plan.get("expected_pin_ids", []),
            "status": outcome, "recommended_route": route, "reason_code": reason,
            "planned_job_count": int(plan.get("planned_job_count", 0)),
            "scored_job_count": sum(item["status"] == "scored" for item in details),
            "decision_details": details,
            "decision_receipt_time": _now(),
        })

    for (stream_id, event_id), jobs in sorted(by_tool.items()):
        pin_outcomes: Dict[str, List[str]] = defaultdict(list)
        incomplete = not stream_quality.get(stream_id, {}).get("complete", True)
        details = []
        for item in jobs:
            result = item["result"] or {}
            meta = item["meta"]
            if result.get("status") != "scored" or not result.get("answers"):
                incomplete = True
                choice = "uncertain"
            else:
                choice = result["answers"]["tool_pin"]["choice"]
            pin_outcomes[meta["pin_id"]].append(choice)
            pin = active_pins.get(meta["pin_id"], {})
            details.append({
                "job_id": item["job_id"], "pin_id": meta["pin_id"],
                "pin_source_event_id": pin.get("source_event_id"),
                "pin_char_span": pin.get("char_span"),
                "pin_timestamp": pin.get("timestamp"),
                "choice": choice, "status": result.get("status", "missing"),
            })
        verdict = "escalate" if incomplete else "allow"
        for pin_id, choices in pin_outcomes.items():
            pin = active_pins.get(pin_id, {})
            if "conflict" in choices and pin.get("status") == "durable_assertion":
                verdict = "deny"
                break
            if "uncertain" in choices or "conflict" in choices:
                verdict = "escalate"
        outputs.append({
            "schema_version": 1, "record_type": "tool_gate_aggregate",
            "run_id": jobs[0]["meta"].get("run_id"),
            "event_id": event_id, "stream_sha256": _hash_id(stream_id),
            "source_file_sha256": jobs[0]["meta"].get("source_file_sha256"),
            "source_line": jobs[0]["meta"].get("source_line"),
            "source_timestamp": jobs[0]["meta"].get("source_timestamp"),
            "status": "incomplete" if incomplete else "scored",
            "verdict": verdict,
            "recommended_route": ("rethink_plan" if verdict == "deny"
                                  else "escalate" if verdict == "escalate"
                                  else "proceed"),
            "reason_code": ("durable_intent_conflict" if verdict == "deny"
                            else "tool_pin_uncertain_or_coverage_incomplete"
                            if verdict == "escalate" else "tool_compatible_with_active_intent"),
            "expected_pin_ids": sorted(pin_outcomes),
            "pin_outcomes": {pin_id: values for pin_id, values in sorted(pin_outcomes.items())},
            "pair_job_count": len(jobs), "pair_job_details": details,
            "decision_receipt_time": _now(), "created_at": _now(),
        })

    processed_research: set[Tuple[str, str]] = set()
    for (stream_id, event_id), jobs in sorted(by_research.items()):
        key = (_hash_id(stream_id), event_id)
        processed_research.add(key)
        choices: List[str] = []
        has_missing = False
        details = []
        for item in jobs:
            result = item["result"] or {}
            if result.get("status") != "scored" or not result.get("answers"):
                has_missing = True
                choice = "insufficient"
            else:
                choice = result["answers"]["research_evidence"]["choice"]
            choices.append(choice)
            details.append({
                "job_id": item["job_id"], "choice": choice,
                "status": (item["result"] or {}).get("status", "missing"),
                "claim_source_event_id": item["meta"].get("claim_source_event_id"),
                "claim_source_file_sha256": item["meta"].get("claim_source_file_sha256"),
                "claim_source_line": item["meta"].get("claim_source_line"),
                "claim_span": item["meta"].get("claim_span"),
                "claim_timestamp": item["meta"].get("claim_timestamp"),
                "evidence_event_id": item["meta"].get("evidence_event_id"),
                "evidence_source_event_id": item["meta"].get("evidence_source_event_id"),
                "evidence_source_file_sha256": item["meta"].get("evidence_source_file_sha256"),
                "evidence_source_line": item["meta"].get("evidence_source_line"),
                "evidence_span": item["meta"].get("evidence_span"),
                "evidence_timestamp": item["meta"].get("evidence_timestamp"),
            })
        planned = research_plans.get(key)
        plan_complete = bool(planned and planned.get("status") == "planned")
        pack = planned.get("pack", {}) if planned else {}
        claim_coverage = list(pack.get("claim_coverage", []))
        choices_by_claim: Dict[Tuple[str, Tuple[int, int]], List[str]] = defaultdict(list)
        for detail in details:
            claim_span = detail.get("claim_span")
            if isinstance(claim_span, list) and len(claim_span) == 2:
                claim_key = (str(detail.get("claim_source_event_id", "")),
                             (int(claim_span[0]), int(claim_span[1])))
                choices_by_claim[claim_key].append(str(detail["choice"]))
        claim_results = []
        unsupported_claims = []
        uncertain_claims = []
        needs_more_claims = []
        for claim in claim_coverage:
            raw_span = claim.get("claim_span", [])
            claim_key = (str(claim.get("claim_source_event_id", "")),
                         (int(raw_span[0]), int(raw_span[1]))
                         if isinstance(raw_span, list) and len(raw_span) == 2 else (-1, -1))
            claim_choices = choices_by_claim.get(claim_key, [])
            if not claim_choices or all(choice == "irrelevant" for choice in claim_choices):
                claim_status = "unsupported"
                unsupported_claims.append(claim)
            elif "insufficient" in claim_choices:
                claim_status = "uncertain"
                uncertain_claims.append(claim)
            elif "contradicts" in claim_choices or "relevant_but_incomplete" in claim_choices:
                claim_status = "needs_more"
                needs_more_claims.append(claim)
            elif "supports" in claim_choices:
                claim_status = "supported"
            else:
                claim_status = "unsupported"
                unsupported_claims.append(claim)
            claim_results.append({**claim, "status": claim_status,
                                  "choices": claim_choices})
        unmatched_claims = list(pack.get("unmatched_claim_spans", []))
        if has_missing or not plan_complete:
            outcome = "incomplete"
            route = "escalate"
        elif uncertain_claims:
            outcome = "insufficient"
            route = "escalate"
        elif needs_more_claims:
            outcome = "research_more"
            route = "research_more"
        elif unsupported_claims:
            outcome = "research_more"
            route = "dispatch_verifier"
        elif not claim_coverage:
            outcome = "not_applicable"
            route = None
        else:
            outcome = "ready"
            route = "proceed"
        outputs.append({
            "schema_version": 1, "record_type": "research_gate_aggregate",
            "event_id": event_id, "stream_sha256": _hash_id(stream_id),
            "source_file_sha256": planned.get("source_file_sha256") if planned else None,
            "source_line": planned.get("source_line") if planned else None,
            "source_timestamp": planned.get("source_timestamp") if planned else None,
            "status": outcome, "recommended_route": route,
            "reason_code": ("no_direct_as_of_support" if route == "dispatch_verifier"
                            else "research_coverage_or_evidence_uncertain"
                            if route == "escalate" else "claim_needs_more_evidence"
                            if route == "research_more" else "as_of_evidence_reviewed"),
            "claim_event_ids": list(pack.get("claim_events", [])),
            "lexically_unmatched_claims": unmatched_claims,
            "target_claims": unsupported_claims + needs_more_claims + uncertain_claims,
            "required_source_class": "direct_retrieved_source_content",
            "evidence_decisions": details,
            "claim_decisions": claim_results,
            "planned_job_count": len(jobs), "scored_job_count": sum(
                item["status"] == "scored" for item in details),
            "decision_receipt_time": _now(), "created_at": _now(),
        })
    for key, planned in sorted(research_plans.items()):
        if key in processed_research:
            continue
        no_jobs = int(planned.get("planned_job_count", 0)) == 0
        pack = planned.get("pack", {})
        no_claims = int(pack.get("claim_atoms", 0)) == 0
        outcome = ("not_applicable" if planned.get("status") == "planned" and no_claims
                   else "research_more" if planned.get("status") == "planned" and no_jobs
                   else "incomplete")
        route = ("dispatch_verifier" if outcome == "research_more"
                 else None if outcome == "not_applicable" else "escalate")
        outputs.append({
            "schema_version": 1, "record_type": "research_gate_aggregate",
            "event_id": planned.get("event_id"), "stream_sha256": planned.get("stream_sha256"),
            "source_file_sha256": planned.get("source_file_sha256"),
            "source_line": planned.get("source_line"),
            "source_timestamp": planned.get("source_timestamp"),
            "status": outcome, "recommended_route": route,
            "reason_code": ("no_factual_claim_candidate" if no_claims
                            else "no_matching_as_of_evidence" if no_jobs
                            else "planned_jobs_missing"),
            "claim_event_ids": list(pack.get("claim_events", [])),
            "target_claims": list(pack.get("unmatched_claim_spans", [])),
            "required_source_class": "direct_retrieved_source_content",
            "evidence_decisions": [], "planned_job_count": int(planned.get("planned_job_count", 0)),
            "scored_job_count": 0, "decision_receipt_time": _now(),
            "created_at": _now(),
        })
    return outputs


def _parse_remote_identity(model_path: Path, profile: Mapping[str, Any]) -> None:
    if not model_path.is_dir():
        raise AdapterError("pinned_model_snapshot_directory_missing")
    if model_path.resolve().name != profile["model"]["revision"]:
        raise AdapterError("model_snapshot_path_must_end_in_pinned_revision")


def _load_tokenizer(model_path: Path) -> Any:
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True, use_fast=True)
    except BaseException as exc:
        raise AdapterError("pinned_local_tokenizer_load_failed") from exc
    if not getattr(tokenizer, "is_fast", False):
        raise AdapterError("fast_tokenizer_offsets_required")
    return tokenizer


def _ensure_private_output(path: Path) -> None:
    resolved = path.resolve()
    repo_root = MODULE_ROOT.parents[3]
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        resolved.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            resolved.chmod(0o700)
        return
    raise AdapterError("private_run_output_must_be_outside_repository")


def _run_identity(run_id: str, profile: Mapping[str, Any], profile_hash: str,
                  source_manifest: Mapping[str, Any], workers: int, batch_size: int) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "adapter_id": profile["adapter_id"],
        "adapter_version": profile["adapter_version"],
        "profile_version": profile["profile_version"],
        "profile_sha256": profile_hash,
        "event_contract_version": EVENT_CONTRACT_VERSION,
        "pin_gate_contract_version": PIN_GATE_CONTRACT_VERSION,
        "acknowledgment_gate_contract_version": ACKNOWLEDGMENT_GATE_CONTRACT_VERSION,
        "assistant_boundary_gate_contract_version": ASSISTANT_BOUNDARY_GATE_CONTRACT_VERSION,
        "model": profile["model"],
        "inference": {**profile["inference"], "workers": workers, "batch_size": batch_size},
        "source_files": source_manifest["files"],
        "source_manifest_sha256": source_manifest["source_manifest_sha256"],
        "source_hashes": source_manifest["source_hashes"],
    }


def _load_existing_or_create_manifest(path: Path, identity: Mapping[str, Any]) -> Dict[str, Any]:
    identity_hash = _sha(_canonical(identity))
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AdapterError("run_manifest_unreadable") from exc
        if existing.get("identity_sha256") != identity_hash:
            raise AdapterError("run_id_already_bound_to_different_inputs")
        return existing
    manifest = {"schema_version": 1, "status": "running",
                "identity": dict(identity), "identity_sha256": identity_hash,
                "started_at": _now(), "finished_at": None}
    _write_json_atomic(path, manifest)
    return manifest


def _resolve_results(rows: Mapping[str, Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {job_id: dict(row) for job_id, row in rows.items()}


def inspect_source(source: Path) -> Dict[str, Any]:
    events, report = load_claude_jsonl(source)
    _verify_full_corpus(events, report)
    return {"status": "inspected", "source": _public_source_manifest(report),
            "summary": public_summary(events, report)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Laya-only versioned local DAG replay (no network inference).")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Validate the raw 81-file Claude corpus without inference.")
    inspect.add_argument("--source", required=True)
    inspect.set_defaults(func=command_inspect)
    smoke = sub.add_parser("smoke", help="Run synthetic-only Laya preflight/inference on local workers.")
    smoke.add_argument("--model-dir", required=True)
    smoke.add_argument("--workers", type=int)
    smoke.add_argument("--batch-size", type=int)
    smoke.set_defaults(func=command_smoke)
    run = sub.add_parser("run", help="Run the full raw Claude Laya DAG replay.")
    run.add_argument("--source", required=True)
    run.add_argument("--model-dir", required=True)
    run.add_argument("--output", required=True, help="Private run directory outside the repository.")
    run.add_argument("--run-id", required=True)
    run.add_argument("--workers", type=int)
    run.add_argument("--batch-size", type=int)
    run.add_argument("--execute-local", action="store_true", help="Required explicit local-inference opt-in.")
    run.set_defaults(func=command_run)
    return parser


def _override_inference(profile: Dict[str, Any], workers: Optional[int],
                        batch_size: Optional[int]) -> Tuple[int, int]:
    configured_workers = int(profile["inference"]["workers"])
    configured_batch = int(profile["inference"]["batch_size"])
    workers = configured_workers if workers is None else workers
    batch_size = configured_batch if batch_size is None else batch_size
    if workers < 1 or workers > 4 or batch_size < 1 or batch_size > 16:
        raise AdapterError("worker_or_batch_override_outside_safe_range")
    profile["inference"]["workers"] = workers
    profile["inference"]["batch_size"] = batch_size
    return workers, batch_size


def command_inspect(args: argparse.Namespace) -> int:
    try:
        print(json.dumps(inspect_source(Path(args.source)), ensure_ascii=False, sort_keys=True))
        return 0
    except (AdapterError, SourceIntegrityError, OSError, ValueError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc).split(":", 1)[0]}, sort_keys=True))
        return 2


def command_smoke(args: argparse.Namespace) -> int:
    try:
        profile = load_profile()
        workers, batch_size = _override_inference(profile, args.workers, args.batch_size)
        model_path = Path(args.model_dir)
        _parse_remote_identity(model_path, profile)
        profile_hash = profile_fingerprint(profile)
        synthetic = _synthetic_jobs(profile, profile_hash, workers, batch_size)
        # Smoke uses a private temporary directory under the system temp root;
        # it never reads any transcript or writes a durable run receipt.
        cache_path = Path(os.getenv("TMPDIR", os.getenv("TEMP", "/tmp"))) / (
            "laya-v1-smoke-" + profile_hash[:16] + ".sqlite")
        cache = _OutputCache(cache_path)
        receipt_rows: List[Dict[str, Any]] = []
        pool = _WorkerPool(model_path, profile, workers)
        try:
            ready = pool.wait_ready()
            result_map = pool.infer(synthetic, profile, cache, {}, receipt_rows.append,
                                    run_id="synthetic-smoke", profile_hash=profile_hash)
        finally:
            pool.close()
            cache.close()
        summary = {"status": "passed" if all(row.get("status") == "scored" for row in receipt_rows) else "failed",
                   "model_revision": profile["model"]["revision"],
                   "sdk_version": profile["model"]["sdk_version"],
                   "workers": ready, "synthetic_jobs": len(synthetic),
                   "scored": sum(row.get("status") == "scored" for row in receipt_rows),
                   "results": [{"gate": row.get("gate"), "answers": row.get("answers"),
                                "batch_elapsed_ms": row.get("batch_elapsed_ms"),
                                "amortized_item_ms": row.get("amortized_item_ms"),
                                "token_preflight": row.get("token_preflight")}
                               for row in receipt_rows]}
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0 if summary["status"] == "passed" else 2
    except (AdapterError, OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc).split(":", 1)[0]}, sort_keys=True))
        return 2


def command_run(args: argparse.Namespace) -> int:
    if not args.execute_local:
        print(json.dumps({"status": "not_run", "reason": "explicit_execute_local_required"}))
        return 2
    started = time.monotonic()
    pool: Optional[_WorkerPool] = None
    cache: Optional[_OutputCache] = None
    try:
        profile = load_profile()
        workers, batch_size = _override_inference(profile, args.workers, args.batch_size)
        source = Path(args.source)
        output = Path(args.output)
        _ensure_private_output(output)
        model_path = Path(args.model_dir)
        _parse_remote_identity(model_path, profile)
        verify_event_contract()
        events, report = load_claude_jsonl(source)
        _verify_full_corpus(events, report)
        source_manifest = _public_source_manifest(report)
        profile_hash = profile_fingerprint(profile)
        identity = _run_identity(args.run_id, profile, profile_hash, source_manifest, workers, batch_size)
        manifest_path = output / "manifest.json"
        manifest = _load_existing_or_create_manifest(manifest_path, identity)
        receipts_path = output / "jobs.jsonl"
        existing = _existing_receipts(receipts_path)
        result_rows = dict(existing)
        cache_path = output.parent / "cache" / f"{profile_hash[:24]}.sqlite"
        cache = _OutputCache(cache_path)
        tokenizer = _load_tokenizer(model_path)
        streams = _stream_groups(events)
        atoms_by_event = _event_atoms(
            events, tokenizer, int(profile["inference"]["state_chunk_tokens"]),
            int(profile["inference"]["state_chunk_overlap_tokens"]))
        phase1_jobs, expected_message_pairs = _phase1_jobs(
            args.run_id, profile_hash, profile, streams, atoms_by_event)
        ready_at_start: List[Dict[str, Any]] = []
        pool = _WorkerPool(model_path, profile, workers)
        ready_at_start = pool.wait_ready()
        print(json.dumps({"phase": "intent_and_assistant_boundary_jobs",
                          "planned_jobs": len(phase1_jobs),
                          "expected_user_event_pairs": expected_message_pairs,
                          "workers": workers, "batch_size": batch_size}, sort_keys=True), flush=True)
        phase1_results = pool.infer(phase1_jobs, profile, cache, result_rows,
                                    lambda row: (_append_jsonl(receipts_path, row), result_rows.__setitem__(row["job_id"], row)),
                                    run_id=args.run_id, profile_hash=profile_hash)
        result_rows.update(phase1_results)
        phase2_jobs, deterministic_rows, reduction = _pin_state_and_phase2(
            args.run_id, profile_hash, profile, streams, atoms_by_event,
            phase1_jobs, phase1_results, tokenizer)
        phase2_results = pool.infer(phase2_jobs, profile, cache, result_rows,
                                    lambda row: (_append_jsonl(receipts_path, row), result_rows.__setitem__(row["job_id"], row)),
                                    run_id=args.run_id, profile_hash=profile_hash)
        result_rows.update(phase2_results)
        final_rows = _aggregate_phase2(
            phase2_jobs, phase2_results, deterministic_rows,
            reduction["active_pins"], reduction["phase2"].get("stream_quality", {}),
        )
        aggregate_path = output / "aggregates.jsonl"
        _write_aggregate_rows(aggregate_path, final_rows)
        all_jobs = phase1_jobs + phase2_jobs
        expected_job_ids = {job["job_id"] for job in all_jobs}
        scored = sum(result_rows.get(job_id, {}).get("status") == "scored" for job_id in expected_job_ids)
        incomplete = sum(result_rows.get(job_id, {}).get("status") != "scored" for job_id in expected_job_ids)
        summary = {
            "status": "complete" if incomplete == 0 else "completed_with_incomplete_jobs",
            "run_id": args.run_id,
            "adapter_id": profile["adapter_id"],
            "adapter_version": profile["adapter_version"],
            "profile_version": profile["profile_version"],
            "profile_sha256": profile_hash,
            "event_contract_version": EVENT_CONTRACT_VERSION,
            "pin_gate_contract_version": PIN_GATE_CONTRACT_VERSION,
            "acknowledgment_gate_contract_version": ACKNOWLEDGMENT_GATE_CONTRACT_VERSION,
            "assistant_boundary_gate_contract_version": ASSISTANT_BOUNDARY_GATE_CONTRACT_VERSION,
            "model": profile["model"],
            "source": {"files": report.files, "rows": report.rows,
                       "events": len(events), "duplicate_rows": report.duplicate_rows,
                       "malformed_rows": report.malformed_rows,
                       "streams": len(streams),
                       "source_manifest_sha256": source_manifest["source_manifest_sha256"],
                       "public_event_manifest_sha256": _sha(_canonical(source_manifest["source_hashes"]))},
            "workers": ready_at_start,
            "planned_jobs": len(all_jobs), "scored_jobs": scored,
            "incomplete_jobs": incomplete,
            "phase1": {**reduction["pin_status"], **reduction["assistant_boundaries"],
                       **reduction["relations"],
                       "expected_message_pairs": expected_message_pairs},
            "phase2": reduction["phase2"],
            "receipt_sha256": _file_sha(receipts_path) if receipts_path.exists() else None,
            "aggregate_sha256": _file_sha(aggregate_path),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "finished_at": _now(),
        }
        _write_json_atomic(output / "summary.json", summary)
        manifest.update({"status": summary["status"], "finished_at": summary["finished_at"],
                         "summary_sha256": _file_sha(output / "summary.json")})
        _write_json_atomic(manifest_path, manifest)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0 if incomplete == 0 else 3
    except (AdapterError, SourceIntegrityError, OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc).split(":", 1)[0],
                          "elapsed_seconds": round(time.monotonic() - started, 3)}, sort_keys=True))
        return 2
    finally:
        if pool is not None:
            pool.close()
        if cache is not None:
            cache.close()


def _write_aggregate_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """Atomically rewrite deterministic aggregates; never include source prose."""
    temp = path.with_suffix(path.suffix + ".tmp")
    ordered = sorted(rows, key=lambda row: (
        str(row.get("stream_sha256", "")), str(row.get("event_id", "")),
        str(row.get("record_type", "")), str(row.get("prior_event_id", "")),
    ))
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in ordered:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    os.replace(temp, path)


def _synthetic_jobs(profile: Mapping[str, Any], profile_hash: str,
                    workers: int, batch_size: int) -> List[Dict[str, Any]]:
    """Model compatibility smoke uses only fixed synthetic text."""
    source = SourceLocation(file_sha256="synthetic", line=1)
    cases = [
        ("user_pin_status", "user_pin_status", "synthetic_pin",
         {"human_message_span": "Please keep the model local and preserve exact source IDs."}),
        ("user_message_pair", "user_message_relation", "synthetic_relation",
         {"earlier_user_excerpt": "Keep the model local.",
          "later_user_excerpt": "Also keep the exact source IDs."}),
        ("tool_pin_pair", "tool_pin_relation", "synthetic_tool",
         {"proposed_tool_excerpt": "Read the local source file.",
          "active_user_pin_excerpt": "Do not upload transcript text.",
          "pin_status": "durable_assertion"}),
        ("research_evidence_pair", "research_evidence_relation", "synthetic_research",
         {"claim_excerpt": "The model will be loaded from a local snapshot.",
          "as_of_evidence_excerpt": "Synthetic evidence says the checkpoint is local.",
          "evidence_kind": "synthetic"}),
        ("acknowledgment_response_pair", "acknowledgment_response", "synthetic_ack",
         {"user_intent_excerpt": "Preserve the requested interface and keep the source IDs.",
          "assistant_response_excerpt": "I will preserve the interface and keep the source IDs.",
          "ack_expectation": "required"}),
        ("assistant_boundary_pair", "assistant_boundary", "synthetic_boundary",
         {"assistant_text_span": "Next I will validate the local input and keep the constraints.",
          "assistant_timestamp": "synthetic-time"}),
        ("plan_intent_pair", "plan_pin_relation", "synthetic_plan",
         {"proposed_plan_excerpt": "Next I will validate the local input.",
          "active_user_pin_excerpt": "Keep the process local.",
          "plan_timestamp": "synthetic-time", "intent_timestamp": "synthetic-time",
          "pin_status": "durable_assertion"}),
    ]
    jobs = []
    for group, gate, event_id, state in cases:
        synthetic_event = ReplayEvent(
            event_id=event_id, stream_id="synthetic-stream", session_id="synthetic",
            sequence=len(jobs), timestamp="", kind="human_user", authority="human", source=source,
            uuid=event_id, parent_uuid=None, is_sidechain=False, agent_id=None,
            tool_use_id=None, text="Synthetic smoke only", metadata={},
        )
        jobs.append(_make_job("synthetic-smoke", profile_hash, profile, group, gate,
                              synthetic_event, state, span_id=f"synthetic-span-{len(jobs)}"))
    return jobs


if __name__ == "__main__":
    try:
        args = build_parser().parse_args()
        raise SystemExit(args.func(args))
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted"}), file=sys.stderr)
        raise SystemExit(130)
