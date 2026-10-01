"""Provenance-preserving normalization for private, raw Claude Code JSONL.

The parser never labels or annotates events with expected decisions. Content is
kept in memory for local replay; public summaries omit it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# Versioned public input surface for downstream model-specific adapters. Bump
# this when normalized event fields or their role/kind semantics change.
REPLAY_EVENT_CONTRACT_VERSION = 1


class SourceIntegrityError(ValueError):
    """The source cannot support a clean blind replay."""


@dataclass(frozen=True)
class SourceLocation:
    file_sha256: str
    line: int


@dataclass
class ReplayEvent:
    event_id: str
    stream_id: str
    session_id: str
    sequence: int
    timestamp: str
    kind: str
    authority: str
    source: SourceLocation
    uuid: str
    parent_uuid: Optional[str]
    is_sidechain: bool
    agent_id: Optional[str]
    tool_use_id: Optional[str] = None
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def public_record(self) -> Dict[str, Any]:
        """Return a content-free record safe for aggregate receipts."""
        row = asdict(self)
        row.pop("text", None)
        row["content_sha256"] = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
        # Metadata may include source prose in unknown schemas; only retain a hash.
        raw = json.dumps(self.metadata, sort_keys=True, ensure_ascii=False, default=str)
        row["metadata_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        row["metadata"] = {}
        return row


@dataclass
class SourceReport:
    files: int = 0
    rows: int = 0
    malformed_rows: int = 0
    duplicate_rows: int = 0
    duplicate_sources: List[Dict[str, Any]] = field(default_factory=list)
    events_by_kind: Dict[str, int] = field(default_factory=dict)
    source_hashes: Dict[str, str] = field(default_factory=dict)
    excluded_sources: List[str] = field(default_factory=list)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_row(row: Dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _decision_relevant_row(row: Dict[str, Any]) -> str:
    # Claude repeats the same source message while changing these session
    # bookkeeping fields. They do not change role, text, causal parent or order.
    # `rendered*` is Claude's derived UI/background-task envelope, not the
    # canonical user/assistant message parsed below. Keep the original fields
    # needed by the normalizer, but ignore this display-only wrapper on dedupe.
    volatile = {"promptId", "gitBranch", "origin", "rendered", "renderedInHumanTurn"}

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items() if key not in volatile}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return _canonical_row(clean(row))


def _text_from_block(block: Any) -> str:
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        text = block.get("text")
        if isinstance(text, str):
            return text
        content = block.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(_text_from_block(x) for x in content if _text_from_block(x))
    return ""


def _stream_id(session_id: str, sidechain: bool, agent_id: Optional[str], file_name: str) -> str:
    if sidechain:
        return f"{session_id}:agent:{agent_id or file_name}"
    return f"{session_id}:root"


def _event(
    *, row: Dict[str, Any], file_hash: str, line: int, block_index: int,
    sequence: int, kind: str, authority: str, text: str = "",
    tool_use_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None,
    file_name: str,
) -> ReplayEvent:
    session_id = str(row.get("sessionId") or row.get("session_id") or file_name)
    sidechain = bool(row.get("isSidechain"))
    agent_id = str(row.get("agentId")) if row.get("agentId") else None
    raw_uuid = str(row.get("uuid") or f"row-{line}")
    event_id = f"{raw_uuid}:b{block_index}"
    if sidechain:
        event_id += f":agent:{agent_id or file_name}"
    return ReplayEvent(
        event_id=event_id,
        stream_id=_stream_id(session_id, sidechain, agent_id, file_name),
        session_id=session_id,
        sequence=sequence,
        timestamp=str(row.get("timestamp") or ""),
        kind=kind,
        authority=authority,
        source=SourceLocation(file_sha256=file_hash, line=line),
        uuid=raw_uuid,
        parent_uuid=str(row.get("parentUuid")) if row.get("parentUuid") else None,
        is_sidechain=sidechain,
        agent_id=agent_id,
        tool_use_id=tool_use_id,
        text=text,
        metadata=dict(metadata or {}),
    )


def normalize_claude_rows(
    rows: Iterable[Tuple[int, Dict[str, Any]]],
    *, file_hash: str = "synthetic",
    file_name: str = "synthetic.jsonl",
    report: Optional[SourceReport] = None,
    seen_uuid: Optional[Dict[str, str]] = None,
) -> List[ReplayEvent]:
    """Normalize rows in original file order without reading future rows."""
    result: List[ReplayEvent] = []
    report = report or SourceReport()
    seen_uuid = seen_uuid if seen_uuid is not None else {}
    sequence = 0
    for line, row in rows:
        report.rows += 1
        uuid = row.get("uuid")
        canonical = _decision_relevant_row(row)
        if uuid:
            # Claude may repeat a delegated prompt UUID in several sidechain
            # exports. Keep each agent's copy in its own stream; collapse only
            # repeats of the same UUID within the same stream identity.
            duplicate_key = str(uuid)
            if bool(row.get("isSidechain")):
                duplicate_key += "\0agent:" + str(row.get("agentId") or file_name)
            prior = seen_uuid.get(duplicate_key)
            if prior is not None:
                if prior != canonical:
                    raise SourceIntegrityError(f"conflicting_source_uuid:{uuid}")
                report.duplicate_rows += 1
                report.duplicate_sources.append({"uuid": str(uuid), "file_sha256": file_hash, "line": line})
                continue
            seen_uuid[duplicate_key] = canonical

        row_type = str(row.get("type") or "").lower()
        message = row.get("message") if isinstance(row.get("message"), dict) else {}
        role = str(message.get("role") or row_type).lower()
        content = message.get("content") if message else row.get("content")
        sidechain = bool(row.get("isSidechain"))
        block_index = 0

        def add(kind: str, authority: str, text: str = "", **kwargs: Any) -> None:
            nonlocal sequence, block_index
            event = _event(
                row=row, file_hash=file_hash, line=line, block_index=block_index,
                sequence=sequence, kind=kind, authority=authority, text=text,
                file_name=file_name, **kwargs,
            )
            result.append(event)
            report.events_by_kind[kind] = report.events_by_kind.get(kind, 0) + 1
            sequence += 1
            block_index += 1

        if row_type == "system" and str(row.get("subtype") or "").lower() == "compact_boundary":
            add(
                "compact_boundary", "system", _text_from_block(content),
                metadata=row.get("compactMetadata") or {},
            )
            continue

        blocks = content if isinstance(content, list) else [content]
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                raw_input = block.get("input") or {}
                if not isinstance(raw_input, (dict, list, str, int, float, bool)):
                    raw_input = str(raw_input)
                tool = str(block.get("name") or "unknown")
                text = json.dumps({"name": tool, "input": raw_input}, ensure_ascii=False, sort_keys=True)
                add("tool_call", "agent", text, tool_use_id=str(block.get("id") or "") or None,
                    metadata={"tool_name": tool})
                continue
            if isinstance(block, dict) and block.get("type") == "tool_result":
                add("tool_result", "tool", _text_from_block(block.get("content")),
                    tool_use_id=str(block.get("tool_use_id") or "") or None,
                    metadata={"is_error": bool(block.get("is_error"))})
                continue
            if isinstance(block, dict) and block.get("type") in ("thinking", "redacted_thinking", "signature"):
                # Private chain-of-thought/signatures are not evidence for these gates.
                continue
            text = _text_from_block(block).strip()
            if not text:
                continue
            if role in ("user", "human") or row_type == "user":
                if sidechain:
                    kind, authority = "delegated_prompt", "agent"
                elif bool(row.get("isMeta")):
                    # Claude stores UI/control envelopes as user-role rows too.
                    # Preserve them for provenance, but never promote them into
                    # user intent or a pin candidate.
                    kind, authority = "meta_user", "system"
                else:
                    kind, authority = "human_user", "human"
                add(kind, authority, text)
            elif role == "assistant" or row_type == "assistant":
                add("assistant_text", "agent", text)
        # Keep source control/metadata events out of the decision stream.
    return result


def load_claude_jsonl(root: Path) -> Tuple[List[ReplayEvent], SourceReport]:
    """Load a raw Claude Code source directory; never accepts a harvest fixture."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise SourceIntegrityError("claude_source_directory_missing")
    if any(part.lower() in {"fixtures", "fixture", "gold", "harvest", "reports"} for part in root.parts):
        raise SourceIntegrityError("curated_or_derived_source_path_rejected")
    files = sorted(root.rglob("*.jsonl"), key=lambda p: str(p.relative_to(root)).casefold())
    if not files:
        raise SourceIntegrityError("no_jsonl_sources")

    report = SourceReport(files=len(files))
    events: List[ReplayEvent] = []
    seen_uuid: Dict[str, str] = {}
    for path in files:
        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            raise SourceIntegrityError("source_read_failed") from exc
        source_hash = _sha256(raw_bytes)
        relative = str(path.relative_to(root)).replace("\\", "/")
        # Store only the hashed relative locator in receipts.
        report.source_hashes[hashlib.sha256(relative.encode()).hexdigest()[:16]] = source_hash
        rows: List[Tuple[int, Dict[str, Any]]] = []
        try:
            decoded = raw_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise SourceIntegrityError("source_not_utf8") from exc
        for line_no, raw_line in enumerate(decoded.splitlines(), 1):
            if not raw_line.strip():
                continue
            try:
                value = json.loads(raw_line)
            except json.JSONDecodeError:
                report.malformed_rows += 1
                continue
            if not isinstance(value, dict):
                report.malformed_rows += 1
                continue
            rows.append((line_no, value))
        events.extend(normalize_claude_rows(rows, file_hash=source_hash, file_name=path.name,
                                            report=report, seen_uuid=seen_uuid))
    link_sidechains(events)
    return events, report


def link_sidechains(events: List[ReplayEvent]) -> None:
    """Link a sidechain to an exact Agent tool-call row when source IDs prove it.

    Missing or ambiguous links are explicit. Consumers must not grant the child
    a parent pin/evidence snapshot without a resolved link.
    """
    agent_calls: List[ReplayEvent] = []
    for event in events:
        if event.kind != "tool_call" or str(event.metadata.get("tool_name", "")).lower() != "agent":
            continue
        agent_calls.append(event)

    first_by_stream: Dict[str, ReplayEvent] = {}
    for event in events:
        if not event.is_sidechain or event.kind != "delegated_prompt":
            continue
        previous = first_by_stream.get(event.stream_id)
        if previous is None or event.sequence < previous.sequence:
            first_by_stream[event.stream_id] = event

    for first in first_by_stream.values():
        # Parent UUID is strongest when present. Some Claude exports omit it on
        # delegated prompts, so an exact prompt-content match is a safe fallback.
        candidates = [call for call in agent_calls if call.uuid == first.parent_uuid] if first.parent_uuid else []
        method = "parent_uuid"
        if not candidates:
            matching: List[ReplayEvent] = []
            for call in agent_calls:
                try:
                    parsed = json.loads(call.text)
                    prompt = parsed.get("input", {}).get("prompt") if isinstance(parsed, dict) else None
                except (json.JSONDecodeError, AttributeError):
                    prompt = None
                if isinstance(prompt, str) and prompt == first.text:
                    matching.append(call)
            candidates = matching
            method = "exact_prompt"
        if len(candidates) == 1:
            first.metadata["delegation_link_status"] = "resolved"
            first.metadata["delegated_from_event_id"] = candidates[0].event_id
            first.metadata["delegated_from_stream_id"] = candidates[0].stream_id
            first.metadata["delegation_link_method"] = method
        else:
            first.metadata["delegation_link_status"] = "ambiguous" if candidates else "unresolved"


def public_summary(events: List[ReplayEvent], report: SourceReport) -> Dict[str, Any]:
    by_kind: Dict[str, int] = {}
    by_stream: Dict[str, int] = {}
    for event in events:
        by_kind[event.kind] = by_kind.get(event.kind, 0) + 1
        by_stream[event.stream_id] = by_stream.get(event.stream_id, 0) + 1
    return {
        "files": report.files,
        "rows": report.rows,
        "malformed_rows": report.malformed_rows,
        "duplicate_rows": report.duplicate_rows,
        "events": len(events),
        "events_by_kind": by_kind,
        "streams": len(by_stream),
        "source_hashes": report.source_hashes,
        "content_included": False,
    }
