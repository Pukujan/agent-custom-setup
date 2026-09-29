"""Parse Claude Code session JSONL and jev-gate-pin gate JSONL."""

from __future__ import annotations

import hashlib
import json
import uuid as uuidlib
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .redact import dumps_redacted, redact


def iter_jsonl(path: Path) -> Iterator[Tuple[int, Dict[str, Any]]]:
    """Yield (1-based line_no, object) for non-empty JSONL lines. Skip bad lines."""
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield i, obj


def _session_id(rec: Dict[str, Any]) -> Optional[str]:
    return rec.get("sessionId") or rec.get("session_id")


def _message_role(rec: Dict[str, Any]) -> Optional[str]:
    msg = rec.get("message")
    if isinstance(msg, dict):
        return msg.get("role")
    return None


def _content_blocks(rec: Dict[str, Any]) -> List[Dict[str, Any]]:
    msg = rec.get("message")
    if not isinstance(msg, dict):
        return []
    content = msg.get("content")
    if isinstance(content, list):
        return [c for c in content if isinstance(c, dict)]
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return []


def _record_uuid(rec: Dict[str, Any]) -> str:
    uuid = rec.get("uuid") or rec.get("leafUuid")
    if uuid:
        return str(uuid)
    return hashlib.sha256(
        json.dumps(rec, sort_keys=True, default=str).encode()
    ).hexdigest()[:32]


def _summarize_content(blocks: List[Dict[str, Any]]) -> Any:
    """Compact redacted content summary (avoid storing huge blobs verbatim)."""
    out: List[Dict[str, Any]] = []
    for b in blocks:
        t = b.get("type")
        if t == "text":
            text = b.get("text") or ""
            if len(text) > 2000:
                text = text[:2000] + "…[truncated]"
            out.append({"type": "text", "text": redact(text)})
        elif t == "tool_use":
            out.append(
                {
                    "type": "tool_use",
                    "id": b.get("id"),
                    "name": b.get("name"),
                    "input": b.get("input"),
                }
            )
        elif t == "tool_result":
            content = b.get("content")
            if isinstance(content, str) and len(content) > 2000:
                content = content[:2000] + "…[truncated]"
            out.append(
                {
                    "type": "tool_result",
                    "tool_use_id": b.get("tool_use_id"),
                    "content": content,
                }
            )
        else:
            out.append({"type": t})
    return out


def extract_claude_records(path: Path) -> Dict[str, Any]:
    """
    Parse a Claude session JSONL into normalized rows.

    Dedupes by record uuid and sorts by (timestamp, uuid) before assigning
    interaction_index so reorder/duplicate lines are metamorphic-stable.
    """
    by_uuid: Dict[str, Dict[str, Any]] = {}
    for _line_no, rec in iter_jsonl(path):
        sid = _session_id(rec)
        if not sid:
            continue
        uid = _record_uuid(rec)
        by_uuid[uid] = rec  # last write wins; identical uuid → same content ideally

    ordered = sorted(
        by_uuid.items(),
        key=lambda kv: (
            str(kv[1].get("timestamp") or ""),
            kv[0],
        ),
    )

    sessions: Dict[str, Dict[str, Any]] = {}
    messages: List[Dict[str, Any]] = []
    tool_calls: Dict[str, Dict[str, Any]] = {}
    interaction_index = 0

    for uuid, rec in ordered:
        sid = _session_id(rec)
        assert sid  # filtered above
        cwd = rec.get("cwd")
        ts = rec.get("timestamp")
        rtype = rec.get("type")

        meta: Dict[str, Any] = {}
        for k in ("version", "gitBranch", "entrypoint", "model", "slug"):
            if rec.get(k) is not None:
                meta[k] = rec.get(k)
        msg = rec.get("message")
        if isinstance(msg, dict) and msg.get("model"):
            meta["model"] = msg.get("model")

        sess = sessions.setdefault(
            sid,
            {"session_id": sid, "cwd": cwd, "started_at": ts, "ended_at": ts, "meta": meta},
        )
        if cwd:
            sess["cwd"] = cwd
        if ts:
            if not sess["started_at"] or ts < sess["started_at"]:
                sess["started_at"] = ts
            if not sess["ended_at"] or ts > sess["ended_at"]:
                sess["ended_at"] = ts
        if meta:
            sess["meta"].update(meta)

        role = _message_role(rec)
        blocks = _content_blocks(rec)

        if rtype == "user" or role == "user":
            interaction_index += 1

        messages.append(
            {
                "uuid": uuid,
                "session_id": sid,
                "parent_uuid": rec.get("parentUuid"),
                "role": role,
                "type": rtype,
                "timestamp": ts,
                "content_redacted": dumps_redacted(_summarize_content(blocks)),
                "interaction_index": interaction_index if interaction_index > 0 else None,
            }
        )

        for b in blocks:
            if b.get("type") == "tool_use":
                tool_id = b.get("id") or f"tool-{uuid}"
                prev = tool_calls.get(tool_id, {})
                tool_calls[tool_id] = {
                    "uuid": tool_id,
                    "session_id": sid,
                    "message_uuid": uuid,
                    "tool_name": redact(str(b.get("name") or "")),
                    "tool_use_id": tool_id,
                    "input_redacted": dumps_redacted(b.get("input")),
                    "result_redacted": prev.get("result_redacted"),
                    "timestamp": ts,
                    "interaction_index": interaction_index if interaction_index > 0 else None,
                }
            elif b.get("type") == "tool_result":
                tool_id = b.get("tool_use_id")
                if not tool_id:
                    continue
                existing = tool_calls.get(
                    tool_id,
                    {
                        "uuid": tool_id,
                        "session_id": sid,
                        "message_uuid": uuid,
                        "tool_name": None,
                        "tool_use_id": tool_id,
                        "input_redacted": None,
                        "result_redacted": None,
                        "timestamp": ts,
                        "interaction_index": interaction_index if interaction_index > 0 else None,
                    },
                )
                content = b.get("content")
                if isinstance(content, str) and len(content) > 4000:
                    content = content[:4000] + "…[truncated]"
                existing["result_redacted"] = dumps_redacted(content)
                existing["session_id"] = sid
                if ts:
                    existing["timestamp"] = existing.get("timestamp") or ts
                tool_calls[tool_id] = existing

    return {
        "sessions": list(sessions.values()),
        "messages": messages,
        "tool_calls": list(tool_calls.values()),
    }


def extract_gate_events(
    path: Path, default_session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Parse jev-gate-pin style JSONL into gate_events rows."""
    # Dedupe by stable event id so duplicate lines are metamorphic-safe
    by_id: Dict[str, Dict[str, Any]] = {}
    for line_no, rec in iter_jsonl(path):
        decision = rec.get("decision")
        tool_name = rec.get("tool_name") or rec.get("toolName") or ""
        if not decision and not tool_name:
            continue
        ts = rec.get("ts") or rec.get("timestamp")
        reason = rec.get("reason_code") or rec.get("reasonCode") or ""
        judge = rec.get("judge") or "mock"
        notes = rec.get("notes") or ""
        sid = rec.get("session_id") or rec.get("sessionId") or default_session_id
        eid = rec.get("uuid") or rec.get("id")
        if not eid:
            # Stable id without line_no so duplicates collapse
            raw = json.dumps(
                {
                    "ts": ts,
                    "decision": decision,
                    "tool_name": tool_name,
                    "reason_code": reason,
                    "session_id": sid,
                    "notes": notes,
                },
                sort_keys=True,
            )
            eid = str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, raw))
        by_id[str(eid)] = {
            "uuid": str(eid),
            "session_id": sid,
            "ts": ts,
            "decision": decision,
            "tool_name": redact(str(tool_name)),
            "reason_code": reason,
            "judge": judge,
            "notes_redacted": redact(str(notes)),
            "payload_redacted": dumps_redacted(rec),
        }
    return list(by_id.values())
