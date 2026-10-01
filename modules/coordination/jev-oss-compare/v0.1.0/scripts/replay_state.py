"""Deterministic, model-free state reducer for blind transcript replay.

The caller supplies already validated model outputs. This module validates
their schemas and applies them to one stream at a time; it never invokes a
model, fetches evidence, or executes historical tools.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from replay_core import UserPair, compact_retention, public_evidence_ledger
from replay_sources import ReplayEvent


class ReplayStateError(ValueError):
    """An event or decision cannot be applied without guessing."""


PIN_STATUSES = frozenset({
    "durable_assertion", "tentative_or_reconsidering", "question_only",
    "context_only", "unclear",
})
RELATIONS = frozenset({
    "unrelated", "same_topic", "asks_about_or_questions",
    "adds_constraint_or_refinement", "supports_or_commits",
    "revises_or_supersedes", "reopens_or_uncertain", "unclear",
})
RESEARCH_OUTCOMES = frozenset({"research_more", "ready", "insufficient"})
TOOL_PIN_OUTCOMES = frozenset({"consistent", "conflict", "unclear", "irrelevant"})
TOOL_VERDICTS = frozenset({"allow", "deny", "escalate"})
COMPACTION_OUTCOMES = frozenset({"preserved", "partially_preserved", "lost", "insufficient"})


def _require_choice(value: Any, choices: Iterable[str], field_name: str) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ReplayStateError(f"invalid_{field_name}")
    return value


def validate_choice_output(output: Any, choices: Iterable[str], *, field_name: str = "choice") -> str:
    """Validate a lane output's selected label without conflating its scores."""
    if not isinstance(output, Mapping) or set(output) - {"choice", "scores", "confidence", "confidence_kind"}:
        raise ReplayStateError("invalid_output_schema")
    return _require_choice(output.get("choice"), choices, field_name)


@dataclass(frozen=True)
class PinCandidate:
    stream_id: str
    event_id: str
    version: int
    status: str
    active: bool = True
    superseded_by: Optional[str] = None
    inherited: bool = False


@dataclass(frozen=True)
class RelationRecord:
    stream_id: str
    prior_event_id: str
    current_event_id: str
    relation: str


@dataclass(frozen=True)
class ToolPinWorkItem:
    stream_id: str
    tool_event_id: str
    pin_event_id: str
    pin_version: int
    pin_status: str
    hard_constraint: bool


@dataclass(frozen=True)
class ResearchSnapshot:
    stream_id: str
    before_event_id: str
    evidence: Tuple[Mapping[str, Any], ...]
    complete: bool
    outcome: Optional[str] = None


@dataclass(frozen=True)
class CompactionRecord:
    stream_id: str
    boundary_event_id: str
    pins: Tuple[Mapping[str, str], ...]
    semantic_status: str = "unknown"


@dataclass(frozen=True)
class ResearchEvidence:
    """Private as-of evidence; ``text`` must never be put in a receipt."""

    event_id: str
    kind: str
    source_event_id: str
    sha256: str
    char_count: int
    text: str = field(repr=False)

    def public_metadata(self) -> Dict[str, Any]:
        return {"event_id": self.event_id, "kind": self.kind,
                "source_event_id": self.source_event_id,
                "sha256": self.sha256, "char_count": self.char_count}


@dataclass(frozen=True)
class ResearchContextChunk:
    index: int
    text: str = field(repr=False)
    evidence_ids: Tuple[str, ...]
    char_count: int

    def public_metadata(self) -> Dict[str, Any]:
        return {"index": self.index, "evidence_ids": list(self.evidence_ids),
                "char_count": self.char_count}


@dataclass(frozen=True)
class ResearchContextPack:
    before_event_id: str
    chunks: Tuple[ResearchContextChunk, ...]
    included_evidence_ids: Tuple[str, ...]
    omitted_evidence_ids: Tuple[str, ...]
    complete: bool
    retrieval_method: str = "chronological"
    query_sha256: Optional[str] = None

    def public_metadata(self) -> Dict[str, Any]:
        return {"before_event_id": self.before_event_id,
                "chunks": [chunk.public_metadata() for chunk in self.chunks],
                "included_evidence_ids": list(self.included_evidence_ids),
                "omitted_evidence_ids": list(self.omitted_evidence_ids),
                "complete": self.complete,
                "retrieval_method": self.retrieval_method,
                "query_sha256": self.query_sha256}


_RESEARCH_TOOLS = frozenset({"read", "webfetch", "websearch", "grep", "glob"})


def _private_research_evidence(prefix: Sequence[ReplayEvent], stream_id: str) -> List[ResearchEvidence]:
    """Extract only already-observed source/tool material and agent claims."""
    ordered = sorted(prefix, key=lambda item: (item.sequence, item.event_id))
    calls: Dict[str, ReplayEvent] = {}
    evidence: List[ResearchEvidence] = []
    for event in ordered:
        if event.stream_id != stream_id:
            raise ReplayStateError("cross_stream_evidence")
        if event.kind == "tool_call" and event.tool_use_id:
            calls[event.tool_use_id] = event
            if str(event.metadata.get("tool_name", "unknown")).lower() in _RESEARCH_TOOLS:
                evidence.append(ResearchEvidence(
                    event_id=event.event_id, kind="source_request",
                    source_event_id=event.event_id,
                    sha256=hashlib.sha256(event.text.encode("utf-8")).hexdigest(),
                    char_count=len(event.text), text=event.text,
                ))
            continue
        if event.kind == "tool_result":
            call = calls.get(event.tool_use_id)
            if call is None:
                continue
            tool_name = str(call.metadata.get("tool_name", "unknown")).lower()
            if tool_name not in _RESEARCH_TOOLS:
                continue
            kind = "retrieved_source"
            source_event_id = call.event_id
        elif event.kind == "assistant_text" and event.authority == "agent":
            kind = "agent_claim"
            source_event_id = event.event_id
        else:
            continue
        evidence.append(ResearchEvidence(
            event_id=event.event_id, kind=kind, source_event_id=source_event_id,
            sha256=hashlib.sha256(event.text.encode("utf-8")).hexdigest(),
            char_count=len(event.text), text=event.text,
        ))
    return evidence


def build_research_context(prefix: Sequence[ReplayEvent], *, stream_id: str,
                           before_event_id: str, max_chars_per_chunk: int,
                           max_chunks: int, query: str = "") -> ResearchContextPack:
    """Build deterministic private research input from an as-of event prefix.

    Context is character-bounded rather than token-bounded; the caller must
    apply the backend's tokenizer budget before inference. Every chunk includes
    whole evidence items only. Oversized/over-limit items are reported omitted
    and force ``complete=False``. No future event may appear in ``prefix``.
    """
    if max_chars_per_chunk < 1 or max_chunks < 1:
        raise ReplayStateError("invalid_research_context_budget")
    if not before_event_id:
        raise ReplayStateError("missing_research_boundary_id")
    for item in prefix:
        if item.stream_id != stream_id:
            raise ReplayStateError("cross_stream_evidence")
        if item.event_id == before_event_id:
            raise ReplayStateError("research_context_lookahead")
    evidence = _private_research_evidence(prefix, stream_id)
    retrieval_method = "chronological"
    query_hash = None
    relevant_ids: set[str] = set()
    if query.strip():
        import re
        stopwords = {"about", "after", "again", "against", "being", "before", "between",
                     "could", "does", "from", "have", "into", "just", "more", "should",
                     "that", "their", "there", "these", "they", "this", "through", "using",
                     "what", "when", "where", "which", "while", "with", "would", "your"}
        terms = {term for term in re.findall(r"[a-z0-9_./-]{2,}", query.lower())
                 if term not in stopwords and not term.isdigit()}
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
        retrieval_method = "lexical_overlap_v1"
        if terms:
            scored: List[Tuple[int, int, ResearchEvidence]] = []
            for index, item in enumerate(evidence):
                source_terms = set(re.findall(r"[a-z0-9_./-]{2,}", item.text.lower()))
                score = len(terms & source_terms)
                if score:
                    relevant_ids.add(item.event_id)
                    scored.append((score, index, item))
            # Prefer more matching terms, then newer evidence for tied scores.
            scored.sort(key=lambda entry: (-entry[0], -entry[1], entry[2].event_id))
            evidence = [entry[2] for entry in scored]
        else:
            evidence = []
    chunks: List[ResearchContextChunk] = []
    included: List[str] = []
    omitted: List[str] = []
    current_text: List[str] = []
    current_ids: List[str] = []
    current_size = 0

    for item in evidence:
        block = f"[{item.kind} id={item.event_id}]\n{item.text}"
        size = len(block) + (1 if current_text else 0)
        if len(block) > max_chars_per_chunk:
            omitted.append(item.event_id)
            continue
        if current_text and current_size + size > max_chars_per_chunk:
            if len(chunks) >= max_chunks:
                omitted.extend(entry.event_id for entry in evidence
                               if entry.event_id not in included and entry.event_id not in omitted)
                break
            chunks.append(ResearchContextChunk(len(chunks), "\n".join(current_text),
                                                tuple(current_ids), current_size))
            current_text, current_ids, current_size = [], [], 0
            size = len(block)
        if len(chunks) >= max_chunks:
            omitted.append(item.event_id)
            continue
        current_text.append(block)
        current_ids.append(item.event_id)
        current_size += size
        included.append(item.event_id)

    if current_text:
        if len(chunks) < max_chunks:
            chunks.append(ResearchContextChunk(len(chunks), "\n".join(current_text),
                                                tuple(current_ids), current_size))
        else:
            omitted.extend(current_ids)
            included = [event_id for event_id in included if event_id not in set(current_ids)]
    omitted_relevant = (bool(relevant_ids & set(omitted)) if retrieval_method == "lexical_overlap_v1"
                        else bool(omitted))
    return ResearchContextPack(before_event_id, tuple(chunks), tuple(included),
                               tuple(dict.fromkeys(omitted)), not omitted_relevant,
                               retrieval_method, query_hash)


@dataclass
class StreamState:
    """Append-only decision history and active pin view for one stream/lane."""

    stream_id: str
    is_sidechain: bool = False
    delegation_status: Optional[str] = None
    parent_snapshot: Sequence[PinCandidate] = ()
    incomplete_reasons: List[str] = field(default_factory=list)
    human_events: List[ReplayEvent] = field(default_factory=list)
    pins: List[PinCandidate] = field(default_factory=list)
    relations: List[RelationRecord] = field(default_factory=list)
    research: List[ResearchSnapshot] = field(default_factory=list)
    tool_work: List[ToolPinWorkItem] = field(default_factory=list)
    compactions: List[CompactionRecord] = field(default_factory=list)
    last_sequence: Optional[int] = None
    _seen_event_ids: set[str] = field(default_factory=set, repr=False)
    _pin_version: int = 0

    def __post_init__(self) -> None:
        if not self.stream_id:
            raise ReplayStateError("empty_stream_id")
        if self.is_sidechain:
            if self.delegation_status != "resolved":
                self.parent_snapshot = ()
                self.incomplete_reasons.append("sidechain_parent_unresolved")
            else:
                # Snapshot is copied into this lane-local stream and is immutable
                # from the child's point of view. Child events cannot rewrite it.
                inherited = sorted(self.parent_snapshot, key=lambda p: (p.version, p.event_id))
                self.pins.extend(PinCandidate(
                    stream_id=self.stream_id, event_id=p.event_id, version=p.version,
                    status=p.status, active=p.active, superseded_by=p.superseded_by,
                    inherited=True,
                ) for p in inherited if p.active)
                self._pin_version = max((p.version for p in inherited), default=0)
        elif self.parent_snapshot:
            raise ReplayStateError("root_stream_cannot_inherit_parent_state")

    @property
    def complete(self) -> bool:
        return not self.incomplete_reasons

    @property
    def active_pins(self) -> Tuple[PinCandidate, ...]:
        return tuple(sorted((p for p in self.pins if p.active), key=lambda p: (p.version, p.event_id)))

    def _accept_event(self, event: ReplayEvent, expected_kind: str) -> None:
        if event.stream_id != self.stream_id:
            raise ReplayStateError("cross_stream_event")
        if event.kind != expected_kind:
            raise ReplayStateError("unexpected_event_kind")
        if event.event_id in self._seen_event_ids:
            raise ReplayStateError("duplicate_event")
        if self.last_sequence is not None and event.sequence < self.last_sequence:
            raise ReplayStateError("out_of_order_event")
        self._seen_event_ids.add(event.event_id)
        self.last_sequence = event.sequence

    def apply_human_decision(self, event: ReplayEvent, output: Any) -> Tuple[UserPair, ...]:
        """Validate and apply user pin/relation output; returns exhaustive pairs.

        Required output shape: ``pin_status``, ``relations`` keyed by every
        prior human event ID, and explicit ``supersedes`` target IDs. A relation
        label alone never deactivates a pin.
        """
        if event.stream_id != self.stream_id or event.kind != "human_user":
            raise ReplayStateError("unexpected_event")
        if event.authority != "human":
            raise ReplayStateError("nonhuman_user_authority")
        if event.event_id in self._seen_event_ids:
            raise ReplayStateError("duplicate_event")
        if self.last_sequence is not None and event.sequence < self.last_sequence:
            raise ReplayStateError("out_of_order_event")
        if not isinstance(output, Mapping) or set(output) != {"pin_status", "relations", "supersedes"}:
            raise ReplayStateError("invalid_user_decision_schema")
        status = _require_choice(output["pin_status"], PIN_STATUSES, "pin_status")
        prior_ids = [prior.event_id for prior in self.human_events]
        raw_relations = output["relations"]
        if not isinstance(raw_relations, Mapping) or set(raw_relations) != set(prior_ids):
            raise ReplayStateError("incomplete_or_extra_prior_user_relations")
        relation_by_id = {
            prior_id: _require_choice(raw_relations[prior_id], RELATIONS, "relation")
            for prior_id in prior_ids
        }
        raw_supersedes = output["supersedes"]
        if (not isinstance(raw_supersedes, list)
                or any(not isinstance(target, str) for target in raw_supersedes)
                or len(raw_supersedes) != len(set(raw_supersedes))):
            raise ReplayStateError("invalid_supersession_edges")
        prior_pin_ids = {pin.event_id for pin in self.pins if pin.active and not pin.inherited}
        targets = set(raw_supersedes)
        if targets and status not in {"durable_assertion", "tentative_or_reconsidering"}:
            raise ReplayStateError("supersession_requires_explicit_intent_status")
        if not targets.issubset(prior_pin_ids):
            raise ReplayStateError("supersession_target_not_prior_active_pin")
        if any(relation_by_id.get(target) != "revises_or_supersedes" for target in targets):
            raise ReplayStateError("supersession_edge_relation_mismatch")

        # Commit event order only after the supplied decision passed validation.
        self._accept_event(event, "human_user")

        # Explicit edges are the only mechanism that closes older user pins.
        for index, pin in enumerate(self.pins):
            if pin.active and not pin.inherited and pin.event_id in targets:
                self.pins[index] = PinCandidate(
                    stream_id=pin.stream_id, event_id=pin.event_id, version=pin.version,
                    status=pin.status, active=False, superseded_by=event.event_id,
                    inherited=pin.inherited,
                )
        for prior in self.human_events:
            self.relations.append(RelationRecord(
                self.stream_id, prior.event_id, event.event_id, relation_by_id[prior.event_id]
            ))
        pairs = tuple(UserPair(self.stream_id, prior.event_id, event.event_id, prior.text, event.text)
                      for prior in self.human_events)
        if status in {"durable_assertion", "tentative_or_reconsidering", "unclear"}:
            self._pin_version += 1
            self.pins.append(PinCandidate(self.stream_id, event.event_id, self._pin_version, status))
        self.human_events.append(event)
        return pairs

    def research_snapshot(self, event: ReplayEvent, prefix: Sequence[ReplayEvent], *, complete: bool = True) -> ResearchSnapshot:
        """Capture evidence strictly before the boundary event, content-free."""
        if event.stream_id != self.stream_id:
            raise ReplayStateError("cross_stream_event")
        if any(item.stream_id != self.stream_id for item in prefix):
            raise ReplayStateError("cross_stream_evidence")
        if any(item.event_id == event.event_id for item in prefix):
            raise ReplayStateError("research_snapshot_lookahead")
        if any(item.sequence >= event.sequence for item in prefix):
            raise ReplayStateError("research_snapshot_lookahead")
        if self.last_sequence is not None and any(item.sequence > self.last_sequence for item in prefix):
            raise ReplayStateError("research_snapshot_lookahead")
        evidence = tuple(public_evidence_ledger(prefix))
        snap = ResearchSnapshot(self.stream_id, event.event_id, evidence, complete and self.complete)
        self.research.append(snap)
        return snap

    def record_research_outcome(self, snapshot: ResearchSnapshot, outcome: str) -> ResearchSnapshot:
        outcome = _require_choice(outcome, RESEARCH_OUTCOMES, "research_outcome")
        if snapshot.stream_id != self.stream_id or snapshot not in self.research:
            raise ReplayStateError("unknown_research_snapshot")
        updated = ResearchSnapshot(snapshot.stream_id, snapshot.before_event_id, snapshot.evidence,
                                   snapshot.complete, outcome)
        self.research[self.research.index(snapshot)] = updated
        return updated

    def tool_pin_work(self, event: ReplayEvent) -> Tuple[ToolPinWorkItem, ...]:
        """Enumerate every active pin for a tool call, without scoring it."""
        self._accept_event(event, "tool_call")
        items = tuple(ToolPinWorkItem(
            stream_id=self.stream_id, tool_event_id=event.event_id,
            pin_event_id=pin.event_id, pin_version=pin.version,
            pin_status=pin.status, hard_constraint=pin.status == "durable_assertion",
        ) for pin in self.active_pins)
        self.tool_work.extend(items)
        return items

    def validate_tool_decision(self, output: Any, expected_pin_ids: Sequence[str]) -> Tuple[str, Dict[str, str]]:
        """Validate complete per-pin outputs and model-independent aggregate."""
        if not isinstance(output, Mapping) or set(output) != {"verdict", "pins"}:
            raise ReplayStateError("invalid_tool_decision_schema")
        verdict = _require_choice(output["verdict"], TOOL_VERDICTS, "tool_verdict")
        pins = output["pins"]
        if not isinstance(pins, Mapping) or set(pins) != set(expected_pin_ids):
            raise ReplayStateError("incomplete_or_extra_tool_pin_results")
        results = {pin_id: _require_choice(value, TOOL_PIN_OUTCOMES, "tool_pin_outcome")
                   for pin_id, value in pins.items()}
        expected = "deny" if any(value == "conflict" and self._pin(pin_id).status == "durable_assertion"
                                  for pin_id, value in results.items()) else (
            "escalate" if any(value == "unclear" for value in results.values()) or not self.complete else "allow"
        )
        # `irrelevant` and `consistent` are both nonblocking, but tentative and
        # unclear pins are never hard constraints; they require escalation on
        # conflict instead of an unsupported hard deny.
        if any(value == "conflict" and self._pin(pin_id).status != "durable_assertion"
               for pin_id, value in results.items()):
            expected = "escalate"
        if verdict != expected:
            raise ReplayStateError("tool_verdict_violates_aggregate_policy")
        return verdict, results

    def compaction_check(self, boundary: ReplayEvent) -> CompactionRecord:
        """Check exact IDs only; absent IDs have unknown semantic survival."""
        if boundary.kind != "compact_boundary" or boundary.stream_id != self.stream_id:
            raise ReplayStateError("invalid_compaction_boundary")
        checks = tuple(compact_retention(boundary, pin.event_id) for pin in self.active_pins)
        record = CompactionRecord(self.stream_id, boundary.event_id, checks)
        self.compactions.append(record)
        return record

    def _pin(self, event_id: str) -> PinCandidate:
        matches = [pin for pin in self.pins if pin.event_id == event_id and pin.active]
        if len(matches) != 1:
            raise ReplayStateError("unknown_or_ambiguous_pin")
        return matches[0]


def apply_outputs_to_stream(events: Sequence[ReplayEvent], user_outputs: Mapping[str, Any], *,
                            is_sidechain: bool = False,
                            delegation_status: Optional[str] = None,
                            parent_snapshot: Sequence[PinCandidate] = ()) -> StreamState:
    """Reduce a stream's user events in source order; other gates stay explicit."""
    if not events:
        raise ReplayStateError("empty_stream")
    stream_ids = {event.stream_id for event in events}
    if len(stream_ids) != 1:
        raise ReplayStateError("mixed_stream_events")
    state = StreamState(next(iter(stream_ids)), is_sidechain, delegation_status, parent_snapshot)
    for event in sorted(events, key=lambda item: (item.sequence, item.event_id)):
        if event.kind == "human_user":
            if event.event_id not in user_outputs:
                state.incomplete_reasons.append("missing_user_decision")
                # Keep sequence/provenance advancing, but do not invent pin state.
                state._accept_event(event, "human_user")
                state.human_events.append(event)
                continue
            state.apply_human_decision(event, user_outputs[event.event_id])
    return state
