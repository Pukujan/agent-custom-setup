#!/usr/bin/env python3
"""Jev-hosted DAG replay for the raw Claude Code corpus.

Runs the SAME versioned typed-decision DAG as ``runner.py`` (identical job
construction, identical deterministic reducer and aggregate schema) but swaps
the local Laya worker pool for the hosted TypeSafe Jev decisions endpoint
(``POST /api/alpha/decisions``). Job IDs derive from the shared Laya profile
hash, so a Jev run and a Laya run over the same ``--stream`` cover an identical
job set and their route tallies are directly comparable.

It never prints secrets, never reads transcript prose into the report, and only
contacts the Jev endpoint the operator's own OpenRouter key authorizes.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
SCRIPT_ROOT = HERE.parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))
sys.path.insert(0, str(HERE))

import runner as laya  # noqa: E402  (reuse the frozen DAG + helpers)
from replay_sources import load_claude_jsonl  # noqa: E402

JEV_BASE = os.environ.get("ACS_JEV_BASE_URL", "https://openrouter.ai/api/alpha").rstrip("/")
JEV_MODEL = os.environ.get("ACS_JEV_MODEL", "typesafe/jev-1.13")
ADAPTER_ID = "jev-typed-decisions-dag"
ADAPTER_VERSION = "1.0.0"


class JevError(RuntimeError):
    """The hosted Jev lane could not be reached or answered validly."""


def _resolve_key() -> str:
    for name in ("OPENROUTER_API_KEY", "ACS_OPENROUTER_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    db = Path(os.path.expanduser("~")) / ".omp" / "agent" / "agent.db"
    if db.exists():
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
            row = conn.execute(
                "SELECT data FROM auth_credentials WHERE provider='openrouter' "
                "AND credential_type='api_key' LIMIT 1").fetchone()
            conn.close()
            if row:
                key = json.loads(row[0]).get("key", "").strip()
                if key:
                    return key
        except (OSError, sqlite3.Error, ValueError):
            pass
    raise JevError("openrouter_key_missing")


def _state_text(state: Mapping[str, Any]) -> str:
    parts = []
    for key in sorted(state):
        value = state[key]
        if isinstance(value, str):
            parts.append(f"{key}:\n{value}")
        else:
            parts.append(f"{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
    return "\n\n".join(parts)[:6000]


def _question_defs(questions: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for qid, spec in questions.items():
        entry: Dict[str, Any] = {
            "type": spec.get("type", "choice"),
            "instructions": spec.get("instructions", ""),
            "criteria": spec.get("criteria", {}),
        }
        if entry["type"] == "score" and "scale" in spec:
            entry["scale"] = spec["scale"]
        out[qid] = entry
    return out


def _jev_decide(key: str, state: Mapping[str, Any], questions: Mapping[str, Any],
                *, timeout_s: float = 30.0, attempts: int = 3) -> Dict[str, Any]:
    body = json.dumps({
        "model": JEV_MODEL,
        "state": _state_text(state),
        "questions": _question_defs(questions),
    }).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Pukujan/agent-custom-setup",
        "X-Title": "acs-jev-typed-decisions",
    }
    last = "unknown"
    for attempt in range(attempts):
        req = urllib.request.Request(f"{JEV_BASE}/decisions", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200] if exc.fp else ""
            last = f"http_{exc.code}"
            if exc.code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                time.sleep(min(20.0, 1.5 * (2 ** attempt)))
                continue
            raise JevError(f"jev_{last}:{detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = "network"
            if attempt < attempts - 1:
                time.sleep(min(20.0, 1.5 * (2 ** attempt)))
                continue
            raise JevError(f"jev_network:{last}") from exc
    raise JevError(f"jev_exhausted:{last}")


class JevPool:
    """Network inference pool with the same ``infer`` contract as the Laya pool.

    The cache's SQLite connection is only touched on the calling thread: reads
    happen before the fan-out, and scored rows are written back once, after it.
    """

    def __init__(self, key: str, workers: int) -> None:
        self.key = key
        self.workers = workers
        self.cost_usd = 0.0
        self.requests = 0
        self._cache = None

    def attach_cache(self, cache: Any) -> None:
        self._cache = cache

    def infer(self, jobs: Sequence[Dict[str, Any]], profile: Mapping[str, Any],
              cache: Any, existing: Mapping[str, Dict[str, Any]],
              append_receipt: Any, *, run_id: str, profile_hash: str) -> Dict[str, Dict[str, Any]]:
        inferred: Dict[str, Dict[str, Any]] = {}
        pending: List[Dict[str, Any]] = []
        for job in sorted(jobs, key=lambda item: item["job_id"]):
            prior = existing.get(job["job_id"])
            if prior is not None:
                if prior.get("request_sha256") != job["request_hash"]:
                    raise laya.AdapterError("resume_request_hash_mismatch")
                inferred[job["job_id"]] = prior
                continue
            cached = cache.get(job["request_hash"])
            if cached is not None:
                row = laya._WorkerPool._receipt_row(job, cached, run_id, profile_hash,
                                                    worker_id=None, batch_id=None, cached=True)
                append_receipt(row)
                inferred[job["job_id"]] = row
                continue
            pending.append(job)

        done = 0
        cache_rows: List[Tuple[str, Mapping[str, Any]]] = []
        with cf.ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {pool.submit(self._one, job, profile, run_id, profile_hash): job for job in pending}
            for future in cf.as_completed(futures):
                job = futures[future]
                row, scored = future.result()
                append_receipt(row)
                inferred[job["job_id"]] = row
                if scored is not None:
                    cache_rows.append((job["request_hash"], scored))
                done += 1
                if done % 25 == 0 or done == len(pending):
                    print(json.dumps({"phase": "jev_model_jobs", "done": done,
                                      "planned": len(pending), "cost_usd": round(self.cost_usd, 6)}),
                          flush=True)
        if cache_rows and self._cache is not None:
            self._cache.put_many(cache_rows)
        return inferred

    def _one(self, job: Dict[str, Any], profile: Mapping[str, Any],
             run_id: str, profile_hash: str):
        t0 = time.perf_counter()
        scored = None
        try:
            raw = _jev_decide(self.key, job["state"], job["questions"])
            ms = round((time.perf_counter() - t0) * 1000, 3)
            self.requests += 1
            self.cost_usd += float((raw.get("usage") or {}).get("cost") or 0.0)
            clean = laya._sanitize_answers(raw.get("answers") or {}, job["meta"]["question_group"], profile)
            result = {"status": "scored", "answers": clean, "reason_codes": [], "token_preflight": None,
                      "batch_size": 1, "batch_elapsed_ms": ms, "amortized_item_ms": ms,
                      "queue_wait_ms": 0.0, "model": str(raw.get("model") or JEV_MODEL)}
            scored = {"status": "scored", "answers": clean, "token_preflight": None}
        except (laya.AdapterError, JevError, ValueError) as exc:
            ms = round((time.perf_counter() - t0) * 1000, 3)
            result = {"status": "failed", "answers": None, "reason_codes": [str(exc).split(":", 1)[0]],
                      "token_preflight": None, "batch_size": 1, "batch_elapsed_ms": ms,
                      "amortized_item_ms": ms, "queue_wait_ms": 0.0, "model": JEV_MODEL}
        row = laya._WorkerPool._receipt_row(job, result, run_id, profile_hash,
                                            worker_id=None, batch_id=None, cached=False)
        return row, scored

    def close(self) -> None:
        return None


def command_run(args: argparse.Namespace) -> int:
    if not args.execute_live:
        print(json.dumps({"status": "not_run", "reason": "explicit_execute_live_required"}))
        return 2
    started = time.monotonic()
    pool: Optional[JevPool] = None
    cache = None
    try:
        key = _resolve_key()
        profile = laya.load_profile()
        profile_hash = laya.profile_fingerprint(profile)
        source = Path(args.source)
        output = Path(args.output)
        laya._ensure_private_output(output)
        laya.verify_event_contract()
        events, report = load_claude_jsonl(source)
        laya._verify_full_corpus(events, report)
        source_manifest = laya._public_source_manifest(report)
        identity = {
            "run_id": args.run_id, "adapter_id": ADAPTER_ID, "adapter_version": ADAPTER_VERSION,
            "dag_profile_sha256": profile_hash,
            "model": {"id": JEV_MODEL, "transport": "openrouter-alpha-decisions"},
            "workers": args.workers, "source_files": source_manifest["files"],
            "source_manifest_sha256": source_manifest["source_manifest_sha256"],
            "stream_filter": args.stream,
        }
        manifest_path = output / "manifest.json"
        manifest = laya._load_existing_or_create_manifest(manifest_path, identity)
        receipts_path = output / "jobs.jsonl"
        existing = laya._existing_receipts(receipts_path)
        result_rows = dict(existing)
        cache_path = output.parent / "cache" / f"jev-{profile_hash[:24]}.sqlite"
        cache = laya._OutputCache(cache_path)
        tokenizer = laya._load_tokenizer(Path(args.model_dir))
        streams = laya._stream_groups(events)
        if args.stream:
            matched = {k: v for k, v in streams.items() if args.stream in k}
            if not matched:
                raise laya.AdapterError(f"no_streams_matched_filter:{args.stream}")
            streams = matched
            events = [e for sid in matched for e in matched[sid]]
        atoms = laya._event_atoms(events, tokenizer, int(profile["inference"]["state_chunk_tokens"]),
                                  int(profile["inference"]["state_chunk_overlap_tokens"]))
        phase1_jobs, expected_pairs = laya._phase1_jobs(args.run_id, profile_hash, profile, streams, atoms)
        if args.max_jobs and len(phase1_jobs) > args.max_jobs:
            raise laya.AdapterError(f"planned_jobs_{len(phase1_jobs)}_exceed_max_jobs_{args.max_jobs}")

        def append(row: Mapping[str, Any]) -> None:
            laya._append_jsonl(receipts_path, row)
            result_rows[row["job_id"]] = row

        pool = JevPool(key, args.workers)
        pool.attach_cache(cache)
        print(json.dumps({"phase": "intent_and_assistant_boundary_jobs", "planned_jobs": len(phase1_jobs),
                          "expected_user_event_pairs": expected_pairs, "workers": args.workers,
                          "model": JEV_MODEL}), flush=True)
        phase1_results = pool.infer(phase1_jobs, profile, cache, result_rows, append,
                                    run_id=args.run_id, profile_hash=profile_hash)
        phase2_jobs, deterministic_rows, reduction = laya._pin_state_and_phase2(
            args.run_id, profile_hash, profile, streams, atoms, phase1_jobs, phase1_results, tokenizer)
        if args.max_jobs and len(phase2_jobs) > args.max_jobs:
            raise laya.AdapterError(f"phase2_jobs_{len(phase2_jobs)}_exceed_max_jobs_{args.max_jobs}")
        phase2_results = pool.infer(phase2_jobs, profile, cache, result_rows, append,
                                    run_id=args.run_id, profile_hash=profile_hash)
        final_rows = laya._aggregate_phase2(phase2_jobs, phase2_results, deterministic_rows,
                                            reduction["active_pins"],
                                            reduction["phase2"].get("stream_quality", {}))
        aggregate_path = output / "aggregates.jsonl"
        laya._write_aggregate_rows(aggregate_path, final_rows)
        all_jobs = phase1_jobs + phase2_jobs
        expected_ids = {job["job_id"] for job in all_jobs}
        scored = sum(result_rows.get(jid, {}).get("status") == "scored" for jid in expected_ids)
        incomplete = len(expected_ids) - scored
        routes: Dict[str, int] = {}
        for row in final_rows:
            route = row.get("recommended_route")
            if route:
                routes[route] = routes.get(route, 0) + 1
        summary = {
            "status": "complete" if incomplete == 0 else "completed_with_incomplete_jobs",
            "run_id": args.run_id, "adapter_id": ADAPTER_ID, "adapter_version": ADAPTER_VERSION,
            "profile_version": profile["profile_version"], "dag_profile_sha256": profile_hash,
            "model": {"id": JEV_MODEL, "transport": "openrouter-alpha-decisions", "provider": "TypeSafe"},
            "source": {"files": report.files, "rows": report.rows, "events": len(events),
                       "streams": len(streams), "stream_filter": args.stream,
                       "source_manifest_sha256": source_manifest["source_manifest_sha256"],
                       "public_event_manifest_sha256": laya._sha(laya._canonical(source_manifest["source_hashes"]))},
            "workers": args.workers, "planned_jobs": len(all_jobs), "scored_jobs": scored,
            "incomplete_jobs": incomplete, "jev_requests": pool.requests,
            "jev_cost_usd": round(pool.cost_usd, 6), "route_totals": routes,
            "phase1": {**reduction["pin_status"], **reduction["assistant_boundaries"],
                       **reduction["relations"], "expected_message_pairs": expected_pairs},
            "phase2": reduction["phase2"],
            "receipt_sha256": laya._file_sha(receipts_path) if receipts_path.exists() else None,
            "aggregate_sha256": laya._file_sha(aggregate_path),
            "elapsed_seconds": round(time.monotonic() - started, 3), "finished_at": laya._now(),
        }
        laya._write_json_atomic(output / "summary.json", summary)
        manifest.update({"status": summary["status"], "finished_at": summary["finished_at"],
                         "summary_sha256": laya._file_sha(output / "summary.json")})
        laya._write_json_atomic(manifest_path, manifest)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0 if incomplete == 0 else 3
    except (laya.AdapterError, JevError, OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"status": "failed", "reason": str(exc).split(":", 1)[0],
                          "elapsed_seconds": round(time.monotonic() - started, 3)}, sort_keys=True))
        return 2
    finally:
        if pool is not None:
            pool.close()
        if cache is not None:
            cache.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jev-hosted DAG replay (same typed-decision DAG as the Laya runner).")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run the Jev DAG replay against the raw Claude corpus.")
    run.add_argument("--source", required=True)
    run.add_argument("--model-dir", required=True, help="Pinned Laya snapshot dir (tokenizer only; no Laya inference).")
    run.add_argument("--output", required=True, help="Private run directory outside the repository.")
    run.add_argument("--run-id", required=True)
    run.add_argument("--stream", help="Replay only streams matching this session/stream-id substring.")
    run.add_argument("--workers", type=int, default=8)
    run.add_argument("--max-jobs", type=int, default=0, help="Abort if planned jobs exceed this cap (0 = no cap).")
    run.add_argument("--execute-live", action="store_true", help="Required explicit live-hosted-inference opt-in.")
    run.set_defaults(func=command_run)
    return parser


if __name__ == "__main__":
    try:
        _args = build_parser().parse_args()
        raise SystemExit(_args.func(_args))
    except KeyboardInterrupt:
        raise SystemExit(130)
