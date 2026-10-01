from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from replay_sources import normalize_claude_rows
from replay_state import (
    ReplayStateError,
    StreamState,
    apply_outputs_to_stream,
    build_research_context,
    validate_choice_output,
)


def make_events():
    rows = [
        (1, {"type": "user", "uuid": "u1", "sessionId": "s", "message": {"role": "user", "content": "Use the hosted API."}}),
        (2, {"type": "assistant", "uuid": "a1", "sessionId": "s", "message": {"role": "assistant", "content": "I will check the official docs."}}),
        (3, {"type": "assistant", "uuid": "a2", "sessionId": "s", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "WebFetch", "input": {"url": "https://docs.example"}}]}}),
        (4, {"type": "user", "uuid": "r1", "sessionId": "s", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "Official API is free for development."}]}}),
        (5, {"type": "user", "uuid": "u2", "sessionId": "s", "message": {"role": "user", "content": "Actually, use the self-hosted version."}}),
        (6, {"type": "assistant", "uuid": "a3", "sessionId": "s", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "python build.py"}}]}}),
        (7, {"type": "system", "subtype": "compact_boundary", "uuid": "c1", "sessionId": "s", "content": "", "compactMetadata": {"preservedMessages": {"allUuids": ["u1", "r1"]}}}),
        (8, {"type": "user", "uuid": "u3", "sessionId": "s", "message": {"role": "user", "content": "One more human turn."}}),
        (9, {"type": "user", "uuid": "other-u1", "sessionId": "other", "message": {"role": "user", "content": "Different stream."}}),
    ]
    return normalize_claude_rows(rows)


def decision(status, relations=None, supersedes=None):
    return {"pin_status": status, "relations": relations or {}, "supersedes": supersedes or []}


class ReplayStateTests(unittest.TestCase):
    def test_user_schema_is_strict_and_not_every_message_becomes_pin(self):
        events = make_events()
        users = [e for e in events if e.kind == "human_user" and e.stream_id == "s:root"]
        state = StreamState("s:root")
        state.apply_human_decision(users[0], decision("durable_assertion"))
        state.apply_human_decision(users[1], decision("question_only", {users[0].event_id: "asks_about_or_questions"}))
        self.assertEqual(len(state.pins), 1)
        self.assertEqual(state.pins[0].event_id, users[0].event_id)
        self.assertEqual(len(state.relations), 1)
        with self.assertRaisesRegex(ReplayStateError, "incomplete_or_extra_prior_user_relations"):
            state.apply_human_decision(users[2], decision("context_only"))

    def test_pairs_exhaustive_and_stream_isolated(self):
        events = make_events()
        users_s = [e for e in events if e.kind == "human_user" and e.stream_id == "s:root"]
        user_other = next(e for e in events if e.kind == "human_user" and e.stream_id == "other:root")
        outputs = {
            users_s[0].event_id: decision("durable_assertion"),
            users_s[1].event_id: decision("tentative_or_reconsidering", {users_s[0].event_id: "same_topic"}),
            users_s[2].event_id: decision("question_only", {
                users_s[0].event_id: "reopens_or_uncertain",
                users_s[1].event_id: "asks_about_or_questions",
            }),
        }
        state = apply_outputs_to_stream([e for e in events if e.stream_id == "s:root"], outputs)
        self.assertEqual([(p.prior_event_id, p.current_event_id) for p in state.relations], [
            (users_s[0].event_id, users_s[1].event_id),
            (users_s[0].event_id, users_s[2].event_id),
            (users_s[1].event_id, users_s[2].event_id),
        ])
        other = apply_outputs_to_stream([user_other], {user_other.event_id: decision("context_only")})
        self.assertEqual(other.pins, [])
        self.assertEqual(other.relations, [])

    def test_only_explicit_supersession_edge_deactivates_pin(self):
        users = [e for e in make_events() if e.kind == "human_user" and e.stream_id == "s:root"]
        state = StreamState("s:root")
        state.apply_human_decision(users[0], decision("durable_assertion"))
        with self.assertRaisesRegex(ReplayStateError, "supersession_edge_relation_mismatch"):
            state.apply_human_decision(users[1], decision("durable_assertion", {users[0].event_id: "same_topic"}, [users[0].event_id]))
        self.assertEqual(len(state.active_pins), 1)  # invalid output was atomic
        state.apply_human_decision(users[1], decision("durable_assertion", {users[0].event_id: "revises_or_supersedes"}, [users[0].event_id]))
        self.assertEqual([pin.event_id for pin in state.active_pins], [users[1].event_id])
        self.assertEqual(state.pins[0].superseded_by, users[1].event_id)

    def test_question_cannot_deactivate_an_existing_hard_pin(self):
        users = [e for e in make_events() if e.kind == "human_user" and e.stream_id == "s:root"]
        state = StreamState("s:root")
        state.apply_human_decision(users[0], decision("durable_assertion"))
        with self.assertRaisesRegex(ReplayStateError, "supersession_requires_explicit_intent_status"):
            state.apply_human_decision(users[1], decision(
                "question_only", {users[0].event_id: "revises_or_supersedes"}, [users[0].event_id]
            ))
        self.assertEqual([pin.event_id for pin in state.active_pins], [users[0].event_id])

    def test_tool_work_covers_all_active_pins_and_validates_aggregate(self):
        events = make_events()
        users = [e for e in events if e.kind == "human_user" and e.stream_id == "s:root"]
        tool = next(e for e in events if e.kind == "tool_call" and e.tool_use_id == "t2")
        state = StreamState("s:root")
        state.apply_human_decision(users[0], decision("durable_assertion"))
        state.apply_human_decision(users[1], decision("tentative_or_reconsidering", {users[0].event_id: "same_topic"}))
        work = state.tool_pin_work(tool)
        self.assertEqual([item.pin_event_id for item in work], [e.event_id for e in users[:2]])
        valid = {"verdict": "deny", "pins": {users[0].event_id: "conflict", users[1].event_id: "consistent"}}
        self.assertEqual(state.validate_tool_decision(valid, [item.pin_event_id for item in work])[0], "deny")
        with self.assertRaisesRegex(ReplayStateError, "incomplete_or_extra_tool_pin_results"):
            state.validate_tool_decision({"verdict": "deny", "pins": {}}, [item.pin_event_id for item in work])

    def test_non_durable_conflict_escalates_instead_of_denying(self):
        users = [e for e in make_events() if e.kind == "human_user" and e.stream_id == "s:root"]
        tool = next(e for e in make_events() if e.kind == "tool_call" and e.tool_use_id == "t2")
        state = StreamState("s:root")
        state.apply_human_decision(users[0], decision("tentative_or_reconsidering"))
        work = state.tool_pin_work(tool)
        self.assertEqual(state.validate_tool_decision({"verdict": "escalate", "pins": {users[0].event_id: "conflict"}}, [x.pin_event_id for x in work])[0], "escalate")

    def test_research_context_asof_private_text_and_exact_coverage(self):
        events = make_events()
        prefix = [e for e in events if e.stream_id == "s:root" and e.sequence < 4]
        pack = build_research_context(prefix, stream_id="s:root", before_event_id="u2:b0", max_chars_per_chunk=300, max_chunks=2)
        private_text = "\n".join(chunk.text for chunk in pack.chunks)
        self.assertIn("Official API is free for development.", private_text)
        self.assertIn("I will check the official docs.", private_text)
        self.assertNotIn("Actually, use the self-hosted version.", private_text)
        public = json.dumps(pack.public_metadata())
        self.assertNotIn("Official API", public)
        self.assertEqual(set(pack.included_evidence_ids) | set(pack.omitted_evidence_ids), {"a1:b0", "a2:b0", "r1:b0"})
        capped = build_research_context(prefix, stream_id="s:root", before_event_id="u2:b0", max_chars_per_chunk=25, max_chunks=1)
        self.assertFalse(capped.complete)
        self.assertTrue(capped.omitted_evidence_ids)
        with self.assertRaisesRegex(ReplayStateError, "research_context_lookahead"):
            build_research_context(events[:5], stream_id="s:root", before_event_id="u2:b0", max_chars_per_chunk=100, max_chunks=2)

    def test_research_context_uses_deterministic_lexical_retrieval(self):
        events = make_events()
        prefix = [e for e in events if e.stream_id == "s:root" and e.sequence < 4]
        pack = build_research_context(prefix, stream_id="s:root", before_event_id="u2:b0",
                                      max_chars_per_chunk=500, max_chunks=2,
                                      query="Official API free development")
        self.assertEqual(pack.retrieval_method, "lexical_overlap_v1")
        self.assertIsNotNone(pack.query_sha256)
        self.assertIn("r1:b0", pack.included_evidence_ids)

    def test_research_snapshot_only_prior_stream_events(self):
        events = make_events()
        state = StreamState("s:root")
        boundary = next(e for e in events if e.event_id == "u2:b0")
        prior = [e for e in events if e.stream_id == "s:root" and e.sequence < boundary.sequence]
        snap = state.research_snapshot(boundary, prior)
        self.assertTrue(snap.complete)
        self.assertEqual(len(snap.evidence), 1)
        with self.assertRaisesRegex(ReplayStateError, "research_snapshot_lookahead"):
            state.research_snapshot(boundary, prior + [boundary])

    def test_compaction_semantics_remain_unknown(self):
        events = make_events()
        users = [e for e in events if e.kind == "human_user" and e.stream_id == "s:root"]
        boundary = next(e for e in events if e.kind == "compact_boundary")
        state = StreamState("s:root")
        state.apply_human_decision(users[0], decision("durable_assertion"))
        record = state.compaction_check(boundary)
        self.assertEqual(record.pins[0]["source_id_status"], "preserved")
        self.assertEqual(record.semantic_status, "unknown")

    def test_unresolved_sidechain_is_incomplete_and_inherits_nothing(self):
        state = StreamState("child", is_sidechain=True, delegation_status="unresolved")
        self.assertFalse(state.complete)
        self.assertEqual(state.active_pins, ())
        self.assertEqual(state.incomplete_reasons, ["sidechain_parent_unresolved"])

    def test_choice_schema_only_accepts_declared_labels(self):
        self.assertEqual(validate_choice_output({"choice": "ready"}, {"ready", "research_more"}), "ready")
        with self.assertRaisesRegex(ReplayStateError, "invalid_choice"):
            validate_choice_output({"choice": "maybe"}, {"ready", "research_more"})
        with self.assertRaisesRegex(ReplayStateError, "invalid_output_schema"):
            validate_choice_output({"choice": "ready", "transcript": "leak"}, {"ready"})


if __name__ == "__main__":
    unittest.main()
