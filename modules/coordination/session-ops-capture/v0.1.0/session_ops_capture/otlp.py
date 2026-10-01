"""Minimal OTLP/HTTP JSON exporter (stdlib urllib; no OpenTelemetry SDK)."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import DEFAULT_OTLP_ENDPOINT, SERVICE_NAME


def _hex_id(nbytes: int, seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[: nbytes * 2]


def _parse_ts_ns(ts: Optional[str], fallback_ns: int) -> int:
    if not ts:
        return fallback_ns
    try:
        # Support Z and +00:00
        s = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1_000_000_000)
    except (ValueError, TypeError, OSError):
        return fallback_ns


def _attr(key: str, value: Any) -> Dict[str, Any]:
    if value is None:
        return {"key": key, "value": {"stringValue": ""}}
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": str(value)}}


def build_spans_payload(
    *,
    tool_calls: Sequence[Dict[str, Any]],
    gate_events: Sequence[Dict[str, Any]] = (),
    messages: Sequence[Dict[str, Any]] = (),
    sessions: Sequence[Dict[str, Any]] = (),
    service_name: str = SERVICE_NAME,
) -> Dict[str, Any]:
    """Build ExportTraceServiceRequest-compatible OTLP/JSON body."""
    now_ns = time.time_ns()
    spans: List[Dict[str, Any]] = []

    cwd_by_session = {s.get("session_id"): s.get("cwd") for s in sessions}

    for tc in tool_calls:
        sid = tc.get("session_id") or ""
        tid = tc.get("uuid") or tc.get("tool_use_id") or "unknown"
        start_ns = _parse_ts_ns(tc.get("timestamp"), now_ns)
        end_ns = start_ns + 1_000_000  # 1ms placeholder
        trace_id = _hex_id(16, f"trace:{sid}")
        span_id = _hex_id(8, f"span:tool:{tid}")
        attrs = [
            _attr("session_id", sid),
            _attr("cwd", cwd_by_session.get(sid) or ""),
            _attr("tool.name", tc.get("tool_name") or ""),
            _attr("tool.use_id", tid),
            _attr("interaction.index", tc.get("interaction_index") if tc.get("interaction_index") is not None else -1),
            _attr("acs.entity", "tool_call"),
        ]
        spans.append(
            {
                "traceId": trace_id,
                "spanId": span_id,
                "name": f"tool.{tc.get('tool_name') or 'unknown'}",
                "kind": 1,  # INTERNAL
                "startTimeUnixNano": str(start_ns),
                "endTimeUnixNano": str(end_ns),
                "attributes": attrs,
                "status": {"code": 1},  # OK
            }
        )

    for ge in gate_events:
        sid = ge.get("session_id") or ""
        eid = ge.get("uuid") or "gate"
        start_ns = _parse_ts_ns(ge.get("ts"), now_ns)
        end_ns = start_ns + 1_000_000
        trace_id = _hex_id(16, f"trace:{sid or 'gate'}")
        span_id = _hex_id(8, f"span:gate:{eid}")
        attrs = [
            _attr("session_id", sid),
            _attr("cwd", cwd_by_session.get(sid) or ""),
            _attr("tool.name", ge.get("tool_name") or ""),
            _attr("tool.decision", ge.get("decision") or ""),
            _attr("gate.reason_code", ge.get("reason_code") or ""),
            _attr("gate.judge", ge.get("judge") or ""),
            _attr("acs.entity", "gate_event"),
        ]
        spans.append(
            {
                "traceId": trace_id,
                "spanId": span_id,
                "name": f"gate.{ge.get('decision') or 'event'}",
                "kind": 1,
                "startTimeUnixNano": str(start_ns),
                "endTimeUnixNano": str(end_ns),
                "attributes": attrs,
                "status": {"code": 1},
            }
        )

    # Optional lightweight session marker spans from messages (user turns)
    for msg in messages:
        if msg.get("role") != "user" and msg.get("type") != "user":
            continue
        sid = msg.get("session_id") or ""
        mid = msg.get("uuid") or "msg"
        start_ns = _parse_ts_ns(msg.get("timestamp"), now_ns)
        end_ns = start_ns + 1_000_000
        spans.append(
            {
                "traceId": _hex_id(16, f"trace:{sid}"),
                "spanId": _hex_id(8, f"span:msg:{mid}"),
                "name": "interaction.user",
                "kind": 1,
                "startTimeUnixNano": str(start_ns),
                "endTimeUnixNano": str(end_ns),
                "attributes": [
                    _attr("session_id", sid),
                    _attr("cwd", cwd_by_session.get(sid) or ""),
                    _attr("interaction.index", msg.get("interaction_index") if msg.get("interaction_index") is not None else -1),
                    _attr("acs.entity", "message"),
                ],
                "status": {"code": 1},
            }
        )

    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        _attr("service.name", service_name),
                        _attr("telemetry.sdk.language", "python"),
                        _attr("telemetry.sdk.name", "acs.session-ops-capture"),
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {
                            "name": "acs.session-ops-capture",
                            "version": "0.1.0",
                        },
                        "spans": spans,
                    }
                ],
            }
        ]
    }


def export_otlp_http(
    payload: Dict[str, Any],
    endpoint: str = DEFAULT_OTLP_ENDPOINT,
    timeout: float = 15.0,
) -> Tuple[int, str]:
    """
    POST OTLP/JSON to collector. Returns (status_code, body_text).
    Raises urllib.error.URLError on transport failure.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "acs.session-ops-capture/0.1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return int(e.code), body


def rows_to_dicts(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        if hasattr(r, "keys"):
            out.append({k: r[k] for k in r.keys()})
        elif isinstance(r, dict):
            out.append(r)
        else:
            out.append(dict(r))
    return out
