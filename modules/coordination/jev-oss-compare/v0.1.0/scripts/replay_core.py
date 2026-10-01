"""Pure, deterministic walk-forward helpers. They do not perform inference."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from replay_sources import ReplayEvent


@dataclass(frozen=True)
class UserPair:
    stream_id: str
    prior_event_id: str
    current_event_id: str
    prior_text: str
    current_text: str


def all_prior_user_pairs(events: Sequence[ReplayEvent]) -> List[UserPair]:
    """Return the exhaustive ordered pairs for human user messages per stream."""
    prior: Dict[str, List[ReplayEvent]] = {}
    pairs: List[UserPair] = []
    for event in events:
        if event.kind != "human_user" or event.authority != "human":
            continue
        history = prior.setdefault(event.stream_id, [])
        for previous in history:
            pairs.append(UserPair(event.stream_id, previous.event_id, event.event_id,
                                  previous.text, event.text))
        history.append(event)
    return pairs


def prefix_before(events: Sequence[ReplayEvent], event_index: int) -> Sequence[ReplayEvent]:
    """The event prefix visible before the event at event_index."""
    if event_index < 0 or event_index > len(events):
        raise IndexError("event_index_out_of_range")
    return events[:event_index]


def public_evidence_ledger(prefix: Sequence[ReplayEvent]) -> List[Dict[str, Any]]:
    """Evidence metadata seen so far; excludes current/future rows and prose."""
    tool_names = {event.tool_use_id: event.metadata.get("tool_name", "unknown")
                  for event in prefix if event.kind == "tool_call" and event.tool_use_id}
    out: List[Dict[str, Any]] = []
    for event in prefix:
        if event.kind != "tool_result":
            continue
        tool_name = tool_names.get(event.tool_use_id, "unknown")
        if tool_name.lower() not in {"read", "webfetch", "websearch", "grep", "glob"}:
            continue
        out.append({
            "event_id": event.event_id,
            "tool_name": tool_name,
            "source_hash": event.source.file_sha256,
            "result_sha256": hashlib.sha256(event.text.encode("utf-8")).hexdigest(),
            "char_count": len(event.text),
        })
    return out


def compact_retention(boundary: ReplayEvent, pin_event_id: str) -> Dict[str, Any]:
    """Report exact source-ID retention without guessing semantic preservation."""
    if boundary.kind != "compact_boundary":
        raise ValueError("compact_boundary_required")
    preserved = boundary.metadata.get("preservedMessages")
    if not isinstance(preserved, dict):
        return {"pin_event_id": pin_event_id, "source_id_status": "unverifiable", "semantic_status": "unknown"}
    uuids = preserved.get("allUuids")
    if not isinstance(uuids, list):
        uuids = preserved.get("uuids")
    if not isinstance(uuids, list):
        return {"pin_event_id": pin_event_id, "source_id_status": "unverifiable", "semantic_status": "unknown"}
    source_uuid = pin_event_id.split(":b", 1)[0]
    exact = source_uuid in {str(value) for value in uuids}
    return {
        "pin_event_id": pin_event_id,
        "source_id_status": "preserved" if exact else "not_preserved_by_id",
        # Transcript marker has no compacted prose; omitted IDs may have been summarized.
        "semantic_status": "unknown",
    }


_HARD_DENY_PATTERNS = (
    re.compile(r"\b(?:mkfs(?:\.[\w+-]+)?|wipefs)\b", re.I),
    re.compile(r"\bdd\b[^\n;&|]*\bof\s*=\s*[\"']?/dev/", re.I),
    re.compile(r"\bgit\b[^\n;&|]*\bpush\b[^\n;&|]*\s--(?:force|force-with-lease|mirror)\b", re.I),
    re.compile(r"\brm\b[^\n;&|]*(?:\s--recursive|\s-[^\s;&|]*[rR])[^\n;&|]*\s/(?:\s|$|[;&|])", re.I),
    re.compile(r"\brm\b[^\n;&|]*(?:\s--recursive|\s-[^\s;&|]*[rR])[^\n;&|]*\s~(?:/|\s|$|[;&|])", re.I),
    re.compile(r"\bremove-item\b[^\n;&|]*-(?:recurse|recursive)\b[^\n;&|]*-force\b[^\n;&|]*\b(?:C:\\|/|~)(?:\s|$|[;&|])", re.I),
    re.compile(r"\bformat(?:\.com)?\s+[A-Z]:", re.I),
)


def hard_deny_reason(event: ReplayEvent) -> str | None:
    """Model-independent catastrophic patterns; never invokes a model."""
    if event.kind != "tool_call":
        return None
    name = event.metadata.get("tool_name", "")
    if str(name).lower() not in {"bash", "powershell", "shell"}:
        return None
    try:
        payload = json.loads(event.text)
    except json.JSONDecodeError:
        return "unparsed_shell_payload"
    raw_input = payload.get("input") if isinstance(payload, dict) else None
    if isinstance(raw_input, str):
        command = raw_input
    elif isinstance(raw_input, dict):
        command = next((raw_input.get(key) for key in ("command", "cmd", "script", "commandline") if isinstance(raw_input.get(key), str)), "")
    else:
        command = ""
    if not command.strip():
        return None
    return "catastrophic_shell_pattern" if any(pattern.search(command) for pattern in _HARD_DENY_PATTERNS) else None


def content_free_event_counts(events: Iterable[ReplayEvent]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for event in events:
        counts[event.kind] = counts.get(event.kind, 0) + 1
    return counts
