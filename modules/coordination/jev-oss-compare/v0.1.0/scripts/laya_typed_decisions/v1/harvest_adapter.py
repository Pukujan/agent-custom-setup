"""Harvest-export adapter for the bounded LOCAL PILOT only.

Converts the checked-in capped harvest export (claude_full_raw.jsonl;
schema id/kind/source/stream/text/timestamp/when) into ReplayEvents so the
frozen Laya v1 pipeline components can run on this device while the verified
81-file raw corpus is unreachable.

This is NOT the blind replay path: `command_run`/`inspect` keep their
81-file guard untouched. Every artifact produced through this adapter MUST be
labeled capped-harvest, non-blind, non-evidence. Authority classification
follows normalize_claude_rows semantics: subagent prompts are delegated/agent
(M28), control envelopes are meta/system, only plain rows become human pins.
Same-stream identical rows collapse (mirroring replay_sources UUID handling);
conflicting same-id content fails closed.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from replay_sources import ReplayEvent, SourceIntegrityError, SourceLocation

_SUBAGENT = re.compile(r"-agent-|^agent-", re.I)
_CONTROL = re.compile(
    r"Stop hook|command-message|local-command|session is being continued"
    r"|<task|system-reminder|Caveat", re.I)


def classify(row: Dict[str, Any]) -> str:
    kind = str(row.get("kind") or "")
    if kind == "tool":
        return "tool"
    ident = f"{row.get('id','')} {row.get('source','')}"
    if _SUBAGENT.search(ident):
        return "subagent"
    if _CONTROL.search(str(row.get("text") or "")[:120]):
        return "control"
    return "human"


def _tool_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    tool = row.get("tool")
    if isinstance(tool, str):
        try:
            tool = json.loads(tool)
        except json.JSONDecodeError:
            tool = {"name": "unknown", "input": tool}
    if not isinstance(tool, dict):
        tool = {"name": "unknown", "input": str(tool)}
    name = str(tool.get("name") or tool.get("tool") or "unknown")
    raw = tool.get("inputs") if "inputs" in tool else tool.get("input")
    if not isinstance(raw, (dict, list, str, int, float, bool)):
        raw = str(raw)
    return {"name": name, "input": raw}


def _canonical(row: Dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def adapt(rows: List[Dict[str, Any]], *, file_hash: str
          ) -> Tuple[List[ReplayEvent], Dict[str, int]]:
    """Return (events, stats). Stats carry collapsed/conflicting duplicate counts."""
    events: List[ReplayEvent] = []
    seen: Dict[str, str] = {}
    stats = {"rows": len(rows), "collapsed_duplicates": 0}
    for sequence, row in enumerate(rows):
        cls = classify(row)
        stream_id = str(row.get("source") or "unknown")
        dedup_key = f"{cls}\0{row.get('id')}\0{stream_id}"
        canonical = _canonical(row)
        prior = seen.get(dedup_key)
        if prior is not None:
            if prior != canonical:
                raise SourceIntegrityError(
                    f"conflicting_harvest_row:{row.get('id')}")
            stats["collapsed_duplicates"] += 1
            continue
        seen[dedup_key] = canonical
        timestamp = str(row.get("timestamp") or row.get("when") or "")
        common = dict(event_id=str(row.get("id")), stream_id=stream_id,
                      session_id=stream_id, sequence=sequence, timestamp=timestamp,
                      source=SourceLocation(file_sha256=file_hash, line=sequence + 1),
                      uuid=str(row.get("id")), parent_uuid=None,
                      tool_use_id=None, is_sidechain=False, agent_id=None,
                      metadata={})
        if cls == "tool":
            payload = _tool_payload(row)
            events.append(ReplayEvent(**{**common, "kind": "tool_call",
                                         "authority": "agent",
                                         "text": json.dumps(payload, ensure_ascii=False,
                                                            sort_keys=True),
                                         "metadata": {"tool_name": payload["name"]}}))
        elif cls == "subagent":
            events.append(ReplayEvent(**{**common, "kind": "delegated_prompt",
                                         "authority": "agent",
                                         "agent_id": stream_id,
                                         "text": str(row.get("text") or "")}))
        elif cls == "control":
            events.append(ReplayEvent(**{**common, "kind": "meta_user",
                                         "authority": "system",
                                         "text": str(row.get("text") or "")}))
        else:
            events.append(ReplayEvent(**{**common, "kind": "human_user",
                                         "authority": "human",
                                         "text": str(row.get("text") or "")}))
    stats["events"] = len(events)
    return events, stats
