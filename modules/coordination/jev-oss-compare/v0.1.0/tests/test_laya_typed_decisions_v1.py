from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from laya_typed_decisions.v1 import runner  # noqa: E402
from replay_sources import ReplayEvent, SourceLocation  # noqa: E402


class CharTokenizer:
    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        result = {"input_ids": list(range(len(text)))}
        if return_offsets_mapping:
            result["offset_mapping"] = [(index, index + 1) for index in range(len(text))]
        return result


def event(event_id, stream_id, sequence, kind, authority, text, *, line,
          uuid=None, tool_name=None, tool_use_id=None):
    metadata = {"tool_name": tool_name} if tool_name else {}
    return ReplayEvent(
        event_id=event_id, stream_id=stream_id, session_id=stream_id,
        sequence=sequence, timestamp=f"2026-09-29T12:00:{sequence:02d}Z",
        kind=kind, authority=authority,
        source=SourceLocation(file_sha256="a" * 64, line=line),
        uuid=uuid or event_id, parent_uuid=None, is_sidechain=False,
        agent_id=None, tool_use_id=tool_use_id, text=text, metadata=metadata,
    )


def scored_ack(choice):
    return {"status": "scored", "answers": {
        "acknowledgment_response": {"choice": choice},
    }}


class LayaTypedDecisionsV1Tests(unittest.TestCase):
    def setUp(self):
        self.profile = runner.load_profile()
        self.tokenizer = CharTokenizer()
        self.user = event("user-1", "stream-1", 1, "human_user", "human",
                          "Keep the requested behavior and preserve the constraints.",
                          line=1)
        self.atom = runner._atomize(self.user.text, self.tokenizer, 220, 32)[0]
        self.span_id = runner._span_id(self.user.event_id, self.atom)
        self.pin_status = {
            self.span_id: {
                "status": "durable_assertion",
                "ack_expectation": "required",
                "scored": True,
            }
        }

    def test_acknowledgment_uses_only_the_next_assistant_message(self):
        first = event("assistant-first", "stream-1", 2, "assistant_text", "agent",
                      "I will keep the requested behavior.", line=2, uuid="assistant-row")
        second_block = event("assistant-second-block", "stream-1", 3, "assistant_text", "agent",
                             "and preserve the constraints.", line=2, uuid="assistant-row")
        later = event("assistant-later", "stream-1", 5, "assistant_text", "agent",
                      "A later message repeats the full instruction.", line=4)
        rows = [self.user, first, second_block, later]
        response_events = runner._next_assistant_response_events(self.user, rows)
        self.assertEqual([row.event_id for row in response_events],
                         ["assistant-first", "assistant-second-block"])

    def test_missing_next_response_is_an_explicit_reconfirm_route(self):
        next_user = event("user-2", "stream-1", 2, "human_user", "human",
                          "A new user turn.", line=2)
        late_response = event("assistant-late", "stream-1", 3, "assistant_text", "agent",
                              "I will keep the constraints.", line=3)
        jobs, plans, stats = runner._acknowledgment_jobs(
            "run", "profile", self.profile, self.user,
            [self.user, next_user, late_response],
            [self.atom], self.pin_status, self.tokenizer,
        )
        self.assertEqual(jobs, [])
        self.assertEqual(plans[0]["status"], "omitted")
        self.assertEqual(plans[0]["recommended_route"], "reconfirm_intent")
        self.assertEqual(stats["ack_spans_missing_response"], 1)

    def test_explicit_repeat_back_request_requires_ack_even_if_question_only(self):
        request = event("repeat-back", "stream-1", 1, "human_user", "human",
                        "Please repeat your understanding so I can correct it.",
                        line=1)
        atom = runner._atomize(request.text, self.tokenizer, 220, 32)[0]
        span_id = runner._span_id(request.event_id, atom)
        response = event("assistant-1", "stream-1", 2, "assistant_text", "agent",
                         "I understand the request.", line=2)
        statuses = {span_id: {"status": "question_only",
                              "ack_expectation": "required", "scored": True}}
        jobs, plans, _stats = runner._acknowledgment_jobs(
            "run", "profile", self.profile, request, [request, response],
            [atom], statuses, self.tokenizer,
        )
        self.assertEqual(len(jobs), 1)
        self.assertTrue(plans[0]["ack_required"])

    def test_response_chunks_keep_exact_spans_and_emit_useful_route(self):
        first = event("assistant-first", "stream-1", 2, "assistant_text", "agent",
                      "I will keep the requested behavior.", line=2, uuid="assistant-row")
        second_block = event("assistant-second-block", "stream-1", 3, "assistant_text", "agent",
                             "and preserve the constraints.", line=2, uuid="assistant-row")
        later = event("assistant-later", "stream-1", 4, "assistant_text", "agent",
                      "Later text cannot repair the first response.", line=3)
        rows = [self.user, first, second_block, later]
        jobs, plans, _stats = runner._acknowledgment_jobs(
            "run", "profile", self.profile, self.user, rows,
            [self.atom], self.pin_status, self.tokenizer,
        )
        self.assertEqual(len(jobs), 2)
        self.assertEqual(plans[0]["planned_job_ids"], [job["job_id"] for job in jobs])
        self.assertTrue(all(job["meta"]["response_event_id"] in {
            "assistant-first", "assistant-second-block",
        } for job in jobs))
        self.assertTrue(all(job["meta"]["response_span_id"] for job in jobs))
        results = {job["job_id"]: scored_ack("omitted") for job in jobs}
        aggregates = runner._aggregate_phase2(
            jobs, results, plans, active_pins={}, stream_quality={"stream-1": {"complete": True}},
        )
        span = next(row for row in aggregates
                    if row["record_type"] == "acknowledgment_gate_aggregate")
        message = next(row for row in aggregates
                       if row["record_type"] == "acknowledgment_message_aggregate")
        self.assertEqual(span["recommended_route"], "reconfirm_intent")
        self.assertEqual(span["status"], "omitted")
        self.assertEqual(message["recommended_route"], "reconfirm_intent")

    def test_incomplete_acknowledgment_coverage_cannot_proceed(self):
        response = event("assistant-1", "stream-1", 2, "assistant_text", "agent",
                         "I will keep the requested behavior.", line=2)
        jobs, plans, _stats = runner._acknowledgment_jobs(
            "run", "profile", self.profile, self.user, [self.user, response],
            [self.atom], self.pin_status, self.tokenizer,
        )
        aggregate = runner._aggregate_phase2(
            jobs, {}, plans, active_pins={}, stream_quality={"stream-1": {"complete": True}},
        )
        span = next(row for row in aggregate
                    if row["record_type"] == "acknowledgment_gate_aggregate")
        self.assertEqual(span["status"], "incomplete")
        self.assertEqual(span["recommended_route"], "escalate")

    def test_acknowledgment_routes_are_helpful_not_binary(self):
        response = event("assistant-1", "stream-1", 2, "assistant_text", "agent",
                         "A response that may carry the request.", line=2)
        jobs, plans, _stats = runner._acknowledgment_jobs(
            "run", "profile", self.profile, self.user, [self.user, response],
            [self.atom], self.pin_status, self.tokenizer,
        )
        expected = {
            "accurate": ("accurate", "proceed"),
            "partial": ("partial", "reconfirm_intent"),
            "contradicted": ("contradicted", "reconfirm_intent"),
            "omitted": ("omitted", "reconfirm_intent"),
            "unclear": ("incomplete", "escalate"),
        }
        for choice, (status, route) in expected.items():
            with self.subTest(choice=choice):
                results = {job["job_id"]: scored_ack(choice) for job in jobs}
                rows = runner._aggregate_phase2(
                    jobs, results, plans, active_pins={},
                    stream_quality={"stream-1": {"complete": True}},
                )
                aggregate = next(row for row in rows
                                 if row["record_type"] == "acknowledgment_gate_aggregate")
                self.assertEqual((aggregate["status"], aggregate["recommended_route"]),
                                 (status, route))

    def test_research_requests_and_agent_claims_are_not_supporting_evidence(self):
        prompt = event("prompt", "stream-1", 1, "human_user", "human",
                       "The alpha feature is available.", line=1)
        request = event("request", "stream-1", 2, "tool_call", "agent",
                        "search alpha feature", line=2, tool_name="websearch",
                        tool_use_id="use-1")
        claim = event("claim", "stream-1", 3, "assistant_text", "agent",
                      "The alpha feature is available.", line=3)
        boundary = event("boundary", "stream-1", 4, "tool_call", "agent",
                         "write output", line=4, tool_name="write")
        jobs, complete, pack = runner._research_jobs(
            "run", "profile", self.profile, boundary,
            [prompt, request, claim, boundary], [prompt, request, claim],
            self.tokenizer, max_tokens=220, overlap_tokens=32,
        )
        self.assertEqual(jobs, [])
        self.assertTrue(complete)
        self.assertEqual(pack["eligible_evidence_records"], 0)
        self.assertEqual(pack["excluded_non_evidence_records"], 2)
        self.assertEqual(pack["planned_pairs"], 0)

    def test_assistant_prose_gets_a_versioned_boundary_job(self):
        assistant = event("assistant-1", "stream-1", 2, "assistant_text", "agent",
                          "Next I will check the available evidence.", line=2)
        atoms = runner._event_atoms([self.user, assistant], self.tokenizer, 220, 32)
        jobs, _pairs = runner._phase1_jobs(
            "run", "profile", self.profile, {"stream-1": [self.user, assistant]}, atoms,
        )
        boundary_job = next(job for job in jobs
                            if job["meta"]["gate"] == "assistant_boundary")
        result = {"status": "scored", "answers": {
            "assistant_boundary": {"choice": "proposed_plan"},
        }}
        statuses, stats = runner._assistant_boundary_statuses(
            [boundary_job], {boundary_job["job_id"]: result},
        )
        self.assertEqual(statuses[boundary_job["meta"]["span_id"]]["status"], "proposed_plan")
        self.assertEqual(stats["assistant_boundary_scored"], 1)

    def test_plan_conflict_routes_to_rethink_before_tool_execution(self):
        job = {
            "job_id": "plan-job",
            "meta": {"gate": "plan_pin_relation", "stream_id": "stream-1",
                     "event_id": "assistant-1", "run_id": "run",
                     "plan_span_id": "assistant-1#chars-0-20", "pin_id": "pin-1",
                     "pin_source_event_id": "user-1"},
        }
        plan = {
            "record_type": "plan_gate_plan", "run_id": "run",
            "event_id": "assistant-1", "stream_sha256": runner._hash_id("stream-1"),
            "plan_span_id": "assistant-1#chars-0-20", "plan_char_span": [0, 20],
            "source_timestamp": "2026-09-29T12:00:02Z",
            "source_file_sha256": "a" * 64, "source_line": 2,
            "boundary_status": "proposed_plan", "expected_pin_ids": ["pin-1"],
            "planned_job_count": 1, "status": "planned",
        }
        result = {"status": "scored", "answers": {"plan_intent": {"choice": "conflict"}}}
        rows = runner._aggregate_phase2(
            [job], {"plan-job": result}, [plan], {}, {"stream-1": {"complete": True}},
        )
        aggregate = next(row for row in rows if row["record_type"] == "plan_gate_aggregate")
        self.assertEqual(aggregate["recommended_route"], "rethink_plan")
        self.assertEqual(aggregate["plan_span_id"], plan["plan_span_id"])

    def test_only_laya_classified_claims_are_rechecked_before_action(self):
        older_prompt = event("user-old", "stream-1", 1, "human_user", "human",
                             "Earlier task.", line=1)
        old_claim = event("claim-old", "stream-1", 2, "assistant_text", "agent",
                          "The old feature costs money.", line=2)
        current_prompt = event("user-current", "stream-1", 3, "human_user", "human",
                               "New task.", line=3)
        current_claim = event("claim-current", "stream-1", 4, "assistant_text", "agent",
                              "This feature is available.", line=4)
        atoms = runner._event_atoms(
            [older_prompt, old_claim, current_prompt, current_claim], self.tokenizer, 220, 32,
        )
        old_span = runner._span_id(old_claim.event_id, atoms[old_claim.event_id][0])
        current_span = runner._span_id(current_claim.event_id, atoms[current_claim.event_id][0])
        boundary_status = {
            old_span: {"status": "factual_claim"},
            current_span: {"status": "factual_claim"},
        }
        claims = runner._classified_claim_atoms(
            [older_prompt, old_claim, current_prompt, current_claim],
            atoms, boundary_status,
        )
        self.assertEqual([(claim.event_id, atom["start"]) for claim, atom in claims],
                         [("claim-current", 0)])

    def test_tool_conflict_routes_to_rethink_plan(self):
        job = {
            "job_id": "tool-job",
            "meta": {"gate": "tool_pin_relation", "stream_id": "stream-1",
                     "event_id": "tool-1", "run_id": "run", "pin_id": "pin-1"},
        }
        result = {"status": "scored", "answers": {"tool_pin": {"choice": "conflict"}}}
        rows = runner._aggregate_phase2(
            [job], {"tool-job": result}, [], {"pin-1": {"status": "durable_assertion"}},
            {"stream-1": {"complete": True}},
        )
        tool = next(row for row in rows if row["record_type"] == "tool_gate_aggregate")
        self.assertEqual(tool["recommended_route"], "rethink_plan")

    def test_no_as_of_support_recommends_a_bounded_verifier(self):
        plan = {
            "record_type": "research_gate_plan",
            "event_id": "boundary",
            "stream_sha256": runner._hash_id("stream-1"),
            "status": "planned",
            "planned_job_count": 0,
            "pack": {
                "claim_atoms": 1, "claim_events": ["claim-1"],
                "unmatched_claim_spans": [{
                    "claim_source_event_id": "claim-1", "claim_span": [0, 12],
                    "candidate_evidence_event_ids": [], "candidate_evidence_count": 0,
                }],
            },
        }
        rows = runner._aggregate_phase2([], {}, [plan], {}, {})
        research = next(row for row in rows
                        if row["record_type"] == "research_gate_aggregate")
        self.assertEqual(research["recommended_route"], "dispatch_verifier")
        self.assertEqual(research["reason_code"], "no_matching_as_of_evidence")
        self.assertEqual(research["claim_event_ids"], ["claim-1"])


if __name__ == "__main__":
    unittest.main()
