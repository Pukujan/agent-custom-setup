"""Process worker for the isolated Laya typed-decisions v1 profile.

This file deliberately never imports the Jev/OpenJev/Kev lane clients. It loads
one immutable local Laya snapshot and accepts bounded batches from the DAG
coordinator. Raw input states exist only in process memory and IPC queues.
"""
from __future__ import annotations

import importlib.metadata
import json
import math
import os
import queue
import time
from typing import Any, Dict, List, Mapping


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _preflight(agent: Any, states: List[Mapping[str, Any]], questions: Mapping[str, Any],
               *, max_len: int, head_max_len: int) -> List[Dict[str, Any]]:
    """Mirror the pinned builder and reject every state/question truncation."""
    from laya.common import build_sequence, render_options, serialize_state

    tok = agent.tok
    answers: List[Dict[str, Any]] = []
    for state in states:
        failures: List[str] = []
        per_question: Dict[str, Dict[str, int]] = {}
        serialized = serialize_state(state).replace(tok.mask_token, " ")
        state_tokens = len(tok(serialized, add_special_tokens=False)["input_ids"])
        state_room: List[int] = []
        for qid, public_question in questions.items():
            internal = agent._to_internal(public_question)
            qtype = internal["t"]
            option_texts = render_options(internal)
            option_ids = [tok(" " + option.replace(tok.mask_token, " "),
                              add_special_tokens=False)["input_ids"]
                          for option in option_texts]
            instruction_text = "%s question: %s" % (qtype, internal["ins"])
            instruction_ids = tok(instruction_text, add_special_tokens=False)["input_ids"]
            option_head_tokens = sum(1 + len(item) for item in option_ids)
            instruction_room = max(8, head_max_len - option_head_tokens)
            prefix, markers = build_sequence(
                tok, "", internal, max_len=max_len, head_max_len=head_max_len,
            )
            room = max(0, max_len - len(prefix))
            state_room.append(room)
            per_question[qid] = {"state_tokens": state_tokens, "state_room": room,
                                 "instruction_tokens": len(instruction_ids),
                                 "instruction_room": instruction_room,
                                 "option_count": len(option_texts)}
            if len(markers) != len(option_texts):
                failures.append("option_marker_count_mismatch")
            if len(set(tuple(item) for item in option_ids)) != len(option_ids):
                failures.append("options_not_token_distinct")
            if any(len(item) > 48 for item in option_ids):
                failures.append("option_text_would_be_truncated")
            if option_head_tokens > head_max_len - 16:
                failures.append("option_head_budget_would_shrink_options")
            if len(instruction_ids) > instruction_room:
                failures.append("instruction_would_be_truncated")
            if state_tokens > room:
                failures.append("state_would_be_truncated")
        answers.append({
            "status": "ok" if not failures else "incomplete",
            "reason_codes": sorted(set(failures)),
            "question_token_counts": per_question,
            "state_tokens": state_tokens,
            "state_room_min": min(state_room) if state_room else 0,
        })
    return answers


def _clean_prediction(result: Mapping[str, Any], questions: Mapping[str, Any]) -> Dict[str, Any]:
    answers = result.get("answers")
    if not isinstance(answers, Mapping) or set(answers) != set(questions):
        raise ValueError("answer_question_set_mismatch")
    clean: Dict[str, Any] = {}
    for qid, question in questions.items():
        answer = answers.get(qid)
        if not isinstance(answer, Mapping):
            raise ValueError("answer_not_object")
        choice = answer.get("choice")
        labels = question.get("criteria", {})
        if not isinstance(choice, str) or choice not in labels:
            raise ValueError("answer_choice_unknown")
        probs = answer.get("probabilities", {})
        safe_probs: Dict[str, float] = {}
        if isinstance(probs, Mapping):
            for key, value in probs.items():
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    safe_probs[str(key)] = float(value)
        clean[qid] = {
            "choice": choice,
            "probabilities": dict(sorted(safe_probs.items())),
            "confidence": answer.get("confidence") if isinstance(answer.get("confidence"), (int, float)) else None,
            "answer_confidence": answer.get("answer_confidence") if isinstance(answer.get("answer_confidence"), (int, float)) else None,
        }
    return clean


def worker_main(worker_id: int, model_path: str, model_revision: str,
                sdk_version: str, sdk_revision: str, torch_threads: int, max_len: int,
                head_max_len: int, task_queue: Any, result_queue: Any) -> None:
    """Load one pinned model, then service batches until a stop sentinel arrives."""
    try:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        import torch
        torch.set_num_threads(torch_threads)
        torch.set_num_interop_threads(torch_threads)
        distribution = importlib.metadata.distribution("laya")
        observed_sdk = distribution.version
        if observed_sdk != sdk_version:
            raise RuntimeError("laya_sdk_version_mismatch")
        direct_url = distribution.read_text("direct_url.json")
        try:
            source_info = json.loads(direct_url or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("laya_sdk_source_identity_invalid") from exc
        observed_revision = source_info.get("vcs_info", {}).get("commit_id")
        if observed_revision != sdk_revision:
            raise RuntimeError("laya_sdk_revision_mismatch")
        if os.path.basename(os.path.realpath(model_path)) != model_revision:
            raise RuntimeError("model_snapshot_revision_mismatch")
        import laya
        agent = laya.load(os.path.realpath(model_path), device="cpu")
        config = getattr(agent, "cfg", {})
        observed_max = int(config.get("max_len", max_len))
        observed_head = int(config.get("head_max_len", head_max_len))
        if observed_max != max_len or observed_head != head_max_len:
            raise RuntimeError("model_context_config_mismatch")
        if not callable(getattr(agent, "predict_batch", None)):
            raise RuntimeError("pinned_sdk_missing_predict_batch")
        result_queue.put({"kind": "worker_ready", "worker_id": worker_id,
                          "sdk_version": observed_sdk,
                          "sdk_revision": observed_revision,
                          "model_revision": model_revision,
                          "device": str(getattr(agent, "device", "cpu")),
                          "torch_threads": torch_threads,
                          "max_len": observed_max, "head_max_len": observed_head})
    except BaseException as exc:
        result_queue.put({"kind": "worker_start_failed", "worker_id": worker_id,
                          "reason_code": type(exc).__name__})
        return

    while True:
        item = task_queue.get()
        if item is None:
            return
        batch_id = str(item.get("batch_id", ""))
        jobs = item.get("jobs", [])
        questions = item.get("questions", {})
        if not isinstance(jobs, list) or not isinstance(questions, dict) or not jobs:
            result_queue.put({"kind": "batch_failed", "batch_id": batch_id,
                              "worker_id": worker_id, "reason_code": "invalid_batch_envelope"})
            continue
        states = [job["state"] for job in jobs]
        try:
            preflight = _preflight(agent, states, questions,
                                   max_len=max_len, head_max_len=head_max_len)
            accepted_indexes = [index for index, result in enumerate(preflight)
                                if result["status"] == "ok"]
            predictions: Dict[int, Dict[str, Any]] = {}
            elapsed_ms = 0.0
            if accepted_indexes:
                started = time.perf_counter()
                outputs = agent.predict_batch(
                    [states[index] for index in accepted_indexes], questions,
                    batch_size=len(accepted_indexes), max_len=max_len,
                    head_max_len=head_max_len, sort_by_length=False,
                )
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                if len(outputs) != len(accepted_indexes):
                    raise ValueError("batch_result_count_mismatch")
                for index, output in zip(accepted_indexes, outputs):
                    predictions[index] = _clean_prediction(output, questions)
            rows = []
            per_item_ms = elapsed_ms / max(1, len(accepted_indexes))
            for index, job in enumerate(jobs):
                pre = preflight[index]
                rows.append({
                    "job_id": job["job_id"],
                    "status": "scored" if index in predictions else "incomplete",
                    "reason_codes": pre["reason_codes"],
                    "token_preflight": pre,
                    "answers": predictions.get(index),
                    "batch_elapsed_ms": round(elapsed_ms, 3) if index in predictions else None,
                    "amortized_item_ms": round(per_item_ms, 3) if index in predictions else None,
                })
            result_queue.put({"kind": "batch_result", "batch_id": batch_id,
                              "worker_id": worker_id, "rows": rows,
                              "batch_size": len(jobs),
                              "inference_count": len(accepted_indexes),
                              "batch_elapsed_ms": round(elapsed_ms, 3)})
        except BaseException as exc:
            # Don't echo exception text: tokenizer/library errors can include
            # fragments of the private decision request.
            result_queue.put({"kind": "batch_failed", "batch_id": batch_id,
                              "worker_id": worker_id,
                              "reason_code": type(exc).__name__})
