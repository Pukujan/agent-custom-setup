"""Ingest via adapters → SQLite (Pass1) + classify/embed (Pass2) + optional OTLP."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import DEFAULT_OTLP_ENDPOINT, SERVICE_NAME
from .adapters import get_adapter
from .db import SessionOpsDB
from .otlp import build_spans_payload, export_otlp_http, rows_to_dicts
from .pass2 import run_pass2


def ingest_once(
    *,
    jsonl: Optional[Path],
    db_path: Path,
    gate_jsonl: Optional[Path] = None,
    otlp_endpoint: Optional[str] = None,
    export_otlp: bool = True,
    include_messages_in_otlp: bool = False,
    adapter_name: str = "claude-jsonl",
    run_pass2_flag: bool = True,
    force_mock_classify: bool = True,
    force_hash_embed: bool = True,
) -> Dict[str, Any]:
    db = SessionOpsDB(db_path)
    try:
        default_sid = None
        if jsonl is not None:
            result = get_adapter(adapter_name).ingest_path(jsonl)
            for s in result.sessions:
                db.upsert_session(
                    s["session_id"],
                    cwd=s.get("cwd"),
                    started_at=s.get("started_at"),
                    ended_at=s.get("ended_at"),
                    meta=s.get("meta"),
                )
                default_sid = default_sid or s["session_id"]
            for m in result.messages:
                db.upsert_message(m)
            for t in result.tool_calls:
                db.upsert_tool_call(t)
            for g in result.gate_events:
                db.upsert_gate_event(g)

        if gate_jsonl is not None:
            gate = get_adapter("gate-jsonl").ingest_path(
                gate_jsonl, default_session_id=default_sid
            )
            for g in gate.gate_events:
                db.upsert_gate_event(g)

        db.commit()

        pass2_result: Optional[Dict[str, Any]] = None
        if run_pass2_flag:
            pass2_result = run_pass2(
                db,
                force_mock_classify=force_mock_classify,
                force_hash_embed=force_hash_embed,
            )

        counts = db.counts()
        fingerprint = db.fingerprint()

        otlp_result: Optional[Dict[str, Any]] = None
        if export_otlp and otlp_endpoint:
            payload = build_spans_payload(
                tool_calls=rows_to_dicts(db.fetch_tool_calls()),
                gate_events=rows_to_dicts(db.fetch_gate_events()),
                messages=rows_to_dicts(db.fetch_messages()) if include_messages_in_otlp else [],
                sessions=rows_to_dicts(db.fetch_sessions()),
                service_name=SERVICE_NAME,
            )
            n_spans = len(payload["resourceSpans"][0]["scopeSpans"][0]["spans"])
            status, body = export_otlp_http(payload, endpoint=otlp_endpoint)
            otlp_result = {
                "endpoint": otlp_endpoint,
                "status": status,
                "span_count": n_spans,
                "body_preview": (body or "")[:200],
                "ok": 200 <= status < 300,
            }

        return {
            "counts": counts,
            "fingerprint": fingerprint,
            "pass2": pass2_result,
            "otlp": otlp_result,
            "adapter": adapter_name,
        }
    finally:
        db.close()


def _resolve_endpoint(cli_value: Optional[str]) -> str:
    if cli_value:
        return cli_value
    env = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
    )
    if env:
        if env.rstrip("/").endswith("/v1/traces"):
            return env
        return env.rstrip("/") + "/v1/traces"
    return DEFAULT_OTLP_ENDPOINT


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="session-ops-capture",
        description=(
            "ACS-wide session ops capture: adapter JSONL → SQLite + Pass2 "
            "classify/embed + OTLP (Claude adapter #1)."
        ),
    )
    ap.add_argument("--jsonl", type=Path, default=None, help="Transcript JSONL path")
    ap.add_argument(
        "--adapter",
        default="claude-jsonl",
        help="Transcript adapter id (default claude-jsonl; see adapters/)",
    )
    ap.add_argument(
        "--db",
        type=Path,
        required=True,
        help="SQLite buffer path (use gitignored agent-runs location for live)",
    )
    ap.add_argument(
        "--otlp-endpoint",
        default=None,
        help=f"OTLP HTTP traces URL (default {DEFAULT_OTLP_ENDPOINT})",
    )
    ap.add_argument("--gate-jsonl", type=Path, default=None, help="Optional gate JSONL")
    ap.add_argument("--once", action="store_true", help="Ingest once and exit (default)")
    ap.add_argument("--watch", action="store_true", help="Poll JSONL and re-ingest on change")
    ap.add_argument("--watch-interval", type=float, default=2.0, help="Watch poll seconds")
    ap.add_argument("--no-otlp", action="store_true", help="Skip OTLP export")
    ap.add_argument(
        "--otlp-messages",
        action="store_true",
        help="Also emit interaction.user spans from messages",
    )
    ap.add_argument("--no-pass2", action="store_true", help="Skip classify+embed Pass2")
    ap.add_argument(
        "--live-classify",
        action="store_true",
        help="Allow remote classifier when ACS_JEV_CLASSIFIER_URL is set",
    )
    ap.add_argument(
        "--live-embed",
        action="store_true",
        help="Allow sentence-transformers backend when configured/installed",
    )
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    if args.jsonl is None and args.gate_jsonl is None:
        ap.error("at least one of --jsonl or --gate-jsonl is required")

    endpoint = None if args.no_otlp else _resolve_endpoint(args.otlp_endpoint)
    export = not args.no_otlp

    def run() -> Dict[str, Any]:
        return ingest_once(
            jsonl=args.jsonl,
            db_path=args.db,
            gate_jsonl=args.gate_jsonl,
            otlp_endpoint=endpoint,
            export_otlp=export,
            include_messages_in_otlp=args.otlp_messages,
            adapter_name=args.adapter,
            run_pass2_flag=not args.no_pass2,
            force_mock_classify=not args.live_classify,
            force_hash_embed=not args.live_embed,
        )

    if args.watch:
        last_sig = None
        print(f"watching; interval={args.watch_interval}s", flush=True)
        while True:
            sig_parts = []
            for p in (args.jsonl, args.gate_jsonl):
                if p is None:
                    continue
                try:
                    st = p.stat()
                    sig_parts.append(f"{p}:{st.st_mtime_ns}:{st.st_size}")
                except FileNotFoundError:
                    sig_parts.append(f"{p}:missing")
            sig = "|".join(sig_parts)
            if sig != last_sig:
                try:
                    result = run()
                    print(
                        f"ingest ok counts={result['counts']} fp={result['fingerprint'][:12]} "
                        f"pass2={result.get('pass2')} otlp={result.get('otlp')}",
                        flush=True,
                    )
                    last_sig = sig
                except Exception as e:  # noqa: BLE001
                    print(f"ingest error: {e}", file=sys.stderr, flush=True)
            time.sleep(args.watch_interval)
    else:
        result = run()
        print(
            f"ingest ok adapter={result.get('adapter')} counts={result['counts']} "
            f"fingerprint={result['fingerprint']}"
        )
        if result.get("pass2"):
            print(f"pass2={result['pass2']}")
        if result.get("otlp"):
            print(f"otlp={result['otlp']}")
        return 0 if (result.get("otlp") is None or result["otlp"].get("ok")) else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
