from __future__ import annotations

import json
import random
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from laya_typed_decisions.v1 import runner  # noqa: E402
from replay_sources import (  # noqa: E402
    ReplayEvent, SourceIntegrityError, SourceLocation, SourceReport,
    normalize_claude_rows,
)

# Metamorphic suite for the Laya typed-decisions benchmark.
# Each test cites its protocol M-ID from
# docs/BENCHMARK-PROTOCOL-local-blind-replay.md (M01-M28 tables).
# All fixtures are invented generic strings; nothing is transcript-derived.


class CharTokenizer:
    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        result = {"input_ids": list(range(len(text)))}
        if return_offsets_mapping:
            result["offset_mapping"] = [(index, index + 1) for index in range(len(text))]
        return result


def event(event_id, stream_id, sequence, kind, authority, text, *, line,
          uuid=None, tool_name=None, tool_use_id=None, timestamp=None):
    metadata = {"tool_name": tool_name} if tool_name else {}
    return ReplayEvent(
        event_id=event_id, stream_id=stream_id, session_id=stream_id,
        sequence=sequence, timestamp=timestamp or f"2026-09-29T12:00:{sequence:02d}Z",
        kind=kind, authority=authority,
        source=SourceLocation(file_sha256="a" * 64, line=line),
        uuid=uuid or event_id, parent_uuid=None, is_sidechain=False,
        agent_id=None, tool_use_id=tool_use_id, text=text, metadata=metadata,
    )


def row_user(uuid, text, *, sidechain=False, blocks=None):
    row = {"uuid": uuid, "type": "user",
           "message": {"role": "user", "content": blocks or [{"type": "text", "text": text}]}}
    if sidechain:
        row["isSidechain"] = True
    return row


def scored_pin(ack_expectation="not_required"):
    return {"status": "scored", "answers": {
        "pin_status": {"choice": "durable_assertion"},
        "ack_expectation": {"choice": ack_expectation},
    }}


def build_user_jobs(events, profile):
    atoms = runner._event_atoms(events, CharTokenizer(), 220, 32)
    streams = {"stream-1": events}
    jobs, expected_pairs = runner._phase1_jobs(
        "run", "profile", profile, streams, atoms)
    return atoms, jobs, expected_pairs


def pin_job_ids(jobs, only_events=None):
    return {(job["meta"]["event_id"], job["job_id"]): job["request_hash"]
            for job in jobs if job["meta"]["gate"] == "user_pin_status"
            and (only_events is None or job["meta"]["event_id"] in only_events)}


def pair_job_ids(jobs):
    return {(job["meta"]["prior_event_id"], job["meta"]["event_id"],
             job["job_id"]): job["request_hash"] for job in jobs
            if job["meta"]["gate"] == "user_message_relation"}


class SourceAdapterMetamorphicTests(unittest.TestCase):
    """M03/M06/M08/M09/M28 source-normalization invariants."""

    def test_M03_tool_result_under_user_role_is_never_human_intent(self):
        rows = [(1, row_user("u1", "ignored", blocks=[{
            "type": "tool_result", "tool_use_id": "use-1",
            "content": "Command output: 3 files changed."}]))]
        events = normalize_claude_rows(rows)
        self.assertEqual([e.kind for e in events], ["tool_result"])
        self.assertEqual([e.authority for e in events], ["tool"])
        self.assertFalse(any(e.kind == "human_user" for e in events))

    def test_M08_duplicate_identical_uuid_collapses_and_keeps_locations(self):
        row = row_user("dup-1", "Keep the retry budget at three attempts.")
        report = SourceReport()
        events = normalize_claude_rows([(1, row), (2, row)], report=report)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source.line, 1)
        self.assertEqual(report.duplicate_rows, 1)
        self.assertEqual(report.duplicate_sources[0]["line"], 2)
        self.assertEqual(report.duplicate_sources[0]["uuid"], "dup-1")

    def test_M09_reused_uuid_with_conflicting_content_fails_closed(self):
        rows = [(1, row_user("dup-2", "Use sqlite for the buffer.")),
                (2, row_user("dup-2", "Use postgres for the buffer."))]
        with self.assertRaises(SourceIntegrityError):
            normalize_claude_rows(rows)

    def test_M06_compaction_marker_stays_out_of_decision_atoms(self):
        rows = [(1, row_user("u6", "Preserve the constraint.")),
                (2, {"uuid": "cb-1", "type": "system", "subtype": "compact_boundary",
                     "message": {"content": "conversation compacted"},
                     "compactMetadata": {"preservedMessages": {"allUuids": ["u6"]}}})]
        events = normalize_claude_rows(rows)
        kinds = {e.kind for e in events}
        self.assertIn("compact_boundary", kinds)
        boundary = next(e for e in events if e.kind == "compact_boundary")
        self.assertEqual(boundary.authority, "system")
        atoms = runner._event_atoms(events, CharTokenizer(), 220, 32)
        self.assertNotIn(boundary.event_id, atoms)

    def test_M28_sidechain_prompt_and_plan_cannot_become_human_pin(self):
        rows = [(1, row_user("child-prompt", "Delegate: summarize findings.", sidechain=True)),
                (2, {"uuid": "child-plan", "type": "assistant", "isSidechain": True,
                     "message": {"role": "assistant",
                                 "content": [{"type": "text", "text": "I will deploy now."}]}})]
        events = normalize_claude_rows(rows)
        kinds = {e.kind: e.authority for e in events}
        self.assertEqual(kinds.get("delegated_prompt"), "agent")
        self.assertEqual(kinds.get("assistant_text"), "agent")
        self.assertNotIn("human_user", kinds)
        profile = runner.load_profile()
        atoms = runner._event_atoms(events, CharTokenizer(), 220, 32)
        jobs, pairs = runner._phase1_jobs(
            "run", "profile", profile, {"stream-child": events}, atoms)
        self.assertEqual(pin_job_ids(jobs), {})
        self.assertEqual(pairs, 0)


class CoreRuleMetamorphicTests(unittest.TestCase):
    """M06 retention + M10 model-independent hard deny."""

    def test_M06_retention_reports_ids_never_semantic_guess(self):
        boundary = event("cb", "stream-1", 9, "compact_boundary", "system",
                         "marker", line=9)
        boundary = ReplayEvent(**{**boundary.__dict__,
                                  "metadata": {"preservedMessages": {"allUuids": ["user-1"]}}})
        plain = event("u1", "stream-1", 1, "human_user", "human", "text", line=1)
        with self.assertRaises(ValueError):
            runner.compact_retention(plain, "user-1:b0")
        kept = runner.compact_retention(boundary, "user-1:b0")
        self.assertEqual(kept["source_id_status"], "preserved")
        self.assertEqual(kept["semantic_status"], "unknown")
        lost = runner.compact_retention(boundary, "user-9:b0")
        self.assertEqual(lost["source_id_status"], "not_preserved_by_id")
        self.assertEqual(lost["semantic_status"], "unknown")

    def test_M10_hard_deny_is_pre_model_and_kind_scoped(self):
        danger = json.dumps({"name": "bash", "input": "rm -rf / --no-preserve-root"})
        shell = event("t1", "stream-1", 2, "tool_call", "agent", danger,
                      line=2, tool_name="bash")
        self.assertTrue(runner.hard_deny_reason(shell))
        prose = event("a1", "stream-1", 3, "assistant_text", "agent",
                      "rm -rf / would be catastrophic", line=3)
        self.assertIsNone(runner.hard_deny_reason(prose))
        benign = event("t2", "stream-1", 4, "tool_call", "agent",
                       json.dumps({"name": "read", "input": "notes.txt"}),
                       line=4, tool_name="readfile")
        self.assertIsNone(runner.hard_deny_reason(benign))


class Phase1MetamorphicTests(unittest.TestCase):
    """M01/M02/M04/M07/M13/M18/M19/M20/M27 job-construction invariants."""

    def setUp(self):
        self.profile = runner.load_profile()

    def test_M01_unrelated_earlier_turn_only_adds_comparisons(self):
        a = event("u-a", "stream-1", 2, "human_user", "human",
                  "Keep the export format as CSV.", line=2)
        b = event("u-b", "stream-1", 3, "human_user", "human",
                  "Also cap rows at five hundred.", line=3)
        _, base_jobs, base_pairs = build_user_jobs([a, b], self.profile)
        self.assertEqual(base_pairs, 1)
        u0 = event("u-0", "stream-1", 1, "human_user", "human",
                   "What is the weather tool?", line=1)
        _, grown_jobs, grown_pairs = build_user_jobs([u0, a, b], self.profile)
        self.assertEqual(grown_pairs, 3)
        self.assertEqual(pin_job_ids(grown_jobs, {"u-a", "u-b"}),
                         pin_job_ids(base_jobs))
        self.assertTrue(pair_job_ids(base_jobs).items() <= pair_job_ids(grown_jobs).items())
        extra = set(pair_job_ids(grown_jobs)) - set(pair_job_ids(base_jobs))
        self.assertEqual(len(extra), 2)

    def test_M02_assistant_summary_wording_never_creates_human_pins(self):
        user = event("u1", "stream-1", 1, "human_user", "human",
                     "Ship behind a feature flag.", line=1)
        v1 = event("a1", "stream-1", 2, "assistant_text", "agent",
                   "Understood: gated rollout.", line=2)
        v2 = event("a1", "stream-1", 2, "assistant_text", "agent",
                   "Got it, we will flag-gate the release.", line=2)
        _, jobs1, _ = build_user_jobs([user, v1], self.profile)
        _, jobs2, _ = build_user_jobs([user, v2], self.profile)
        self.assertEqual(pin_job_ids(jobs1), pin_job_ids(jobs2))
        self.assertTrue(all(job["meta"]["event_id"] != "a1"
                            for job in jobs1 if job["meta"]["gate"] == "user_pin_status"))

    def test_M04_later_correction_changes_only_its_pair_edge(self):
        u1 = event("u1", "stream-1", 1, "human_user", "human",
                   "Export CSV with a five hundred row cap.", line=1)
        unrelated = event("u2x", "stream-1", 2, "human_user", "human",
                          "Also add a footer line.", line=2)
        correction = event("u2c", "stream-1", 2, "human_user", "human",
                           "Change the row cap to one thousand.", line=2)
        _, base_jobs, _ = build_user_jobs([u1, unrelated], self.profile)
        _, corr_jobs, _ = build_user_jobs([u1, correction], self.profile)
        self.assertEqual(pin_job_ids(base_jobs, {"u1"}), pin_job_ids(corr_jobs, {"u1"}))
        self.assertTrue(any(job["meta"]["gate"] == "user_message_relation"
                            and job["meta"]["event_id"] == "u2c"
                            and job["meta"]["prior_event_id"] == "u1"
                            for job in corr_jobs))
        self.assertTrue(any(job["meta"]["gate"] == "user_message_relation"
                            and job["meta"]["event_id"] == "u2x"
                            and job["meta"]["prior_event_id"] == "u1"
                            for job in base_jobs))
        self.assertEqual(pin_job_ids(base_jobs, {"u1"}),
                         {(j["meta"]["event_id"], j["job_id"]): j["request_hash"]
                          for j in build_user_jobs([u1], self.profile)[1]})

    def test_M07_state_budget_chunks_cover_never_truncate(self):
        text = "constraint alpha; " * 30
        atoms = runner._atomize(text, CharTokenizer(), 220, 32)
        self.assertGreater(len(atoms), 1)
        covered = set()
        for atom in atoms:
            self.assertLessEqual(atom["end"] - atom["start"], 220)
            covered.update(range(atom["start"], atom["end"]))
        self.assertEqual(covered, set(range(len(text))))

    def test_M27_overlap_preserves_split_qualifiers_as_distinct_spans(self):
        text = ("the migration is safe because the schema matches, and "
                "not risky at all since the rollback path is tested fully today")
        atoms = runner._atomize(text, CharTokenizer(), 40, 12)
        self.assertGreater(len(atoms), 2)
        for prior, current in zip(atoms, atoms[1:]):
            self.assertLess(current["start"], prior["end"])
        negation = text.index("not risky")
        holders = [a for a in atoms if a["start"] <= negation < a["end"]]
        self.assertGreaterEqual(len(holders), 1)
        span_ids = {runner._span_id("e1", a) for a in atoms}
        self.assertEqual(len(span_ids), len(atoms))

    def test_M13_future_events_never_change_earlier_job_identity(self):
        u1 = event("u1", "stream-1", 1, "human_user", "human",
                   "Use the staging endpoint only.", line=1)
        _, solo_jobs, _ = build_user_jobs([u1], self.profile)
        later = event("u2", "stream-1", 2, "human_user", "human",
                      "Actually also allow localhost.", line=2)
        _, grown_jobs, _ = build_user_jobs([u1, later], self.profile)
        self.assertEqual(pin_job_ids(grown_jobs, {"u1"}), pin_job_ids(solo_jobs))
        for job in grown_jobs:
            if job["meta"]["gate"] == "user_message_relation":
                self.assertLessEqual(job["meta"]["prior_timestamp"],
                                     job["meta"]["current_timestamp"])

    def test_M18_agent_prose_between_turns_changes_no_relation_edges(self):
        u1 = event("u1", "stream-1", 1, "human_user", "human",
                   "Do not touch the production database.", line=1)
        u2 = event("u2", "stream-1", 4, "human_user", "human",
                   "Proceed with the staging migration.", line=4)
        prose = event("a1", "stream-1", 2, "assistant_text", "agent",
                      "I will summarize the schema first.", line=2)
        tool = event("t1", "stream-1", 3, "tool_call", "agent",
                     json.dumps({"name": "read", "input": "schema"}),
                     line=3, tool_name="read")
        _, base_jobs, base_pairs = build_user_jobs([u1, u2], self.profile)
        _, grown_jobs, grown_pairs = build_user_jobs([u1, prose, tool, u2], self.profile)
        self.assertEqual(pair_job_ids(base_jobs), pair_job_ids(grown_jobs))
        self.assertEqual(pin_job_ids(base_jobs), pin_job_ids(grown_jobs))
        self.assertEqual(base_pairs, grown_pairs)

    def test_M19_pin_status_carries_no_time_expiry_field(self):
        u1 = event("u1", "stream-1", 1, "human_user", "human",
                   "Keep the audit log for ninety days.", line=1,
                   timestamp="2026-09-29T00:00:00Z")
        atoms = runner._event_atoms([u1], CharTokenizer(), 220, 32)
        jobs, _ = runner._phase1_jobs(
            "run", "profile", self.profile, {"stream-1": [u1]}, atoms)
        pin_job = next(job for job in jobs if job["meta"]["gate"] == "user_pin_status")
        statuses, _stats = runner._pin_statuses([pin_job],
                                                {pin_job["job_id"]: scored_pin()})
        status = statuses[pin_job["meta"]["span_id"]]
        self.assertEqual(status["status"], "durable_assertion")
        self.assertFalse(any("expir" in key or "age" in key for key in status))
        delayed = event("u1", "stream-1", 1, "human_user", "human",
                        "Keep the audit log for ninety days.", line=1,
                        timestamp="2026-09-29T10:00:00Z")
        d_atoms = runner._event_atoms([delayed], CharTokenizer(), 220, 32)
        d_jobs, _ = runner._phase1_jobs(
            "run", "profile", self.profile, {"stream-1": [delayed]}, d_atoms)
        d_pin = next(job for job in d_jobs if job["meta"]["gate"] == "user_pin_status")
        d_statuses, _ = runner._pin_statuses([d_pin], {d_pin["job_id"]: scored_pin()})
        d_status = d_statuses[d_pin["meta"]["span_id"]]
        self.assertEqual({k: v for k, v in status.items() if k != "job_id"},
                         {k: v for k, v in d_status.items() if k != "job_id"})

    def test_M20_clause_atoms_keep_supersession_granularity(self):
        text = ("clause one fixes the export format to CSV. " * 2
                + "clause two fixes the row cap at five hundred. " * 2)
        u1 = event("u1", "stream-1", 1, "human_user", "human", text, line=1)
        atoms = runner._atomize(u1.text, CharTokenizer(), 60, 8)
        self.assertGreater(len(atoms), 1)
        span_ids = {runner._span_id("u1", atom) for atom in atoms}
        self.assertEqual(len(span_ids), len(atoms))
        jobs = [runner._make_job("run", "profile", self.profile, "user_pin_status",
                                 "user_pin_status", u1,
                                 {"human_message_span": atom["text"],
                                  "human_message_timestamp": u1.timestamp},
                                 span_id=runner._span_id("u1", atom),
                                 char_span=[atom["start"], atom["end"]])
                for atom in atoms]
        self.assertEqual(len({job["job_id"] for job in jobs}), len(atoms))


class GateAggregateMetamorphicTests(unittest.TestCase):
    """M05/M11/M12/M14+M23/M16/M17/M21/M24/M26 reducer invariants.

    M15, M22 and M25 are proved by existing cases in
    test_laya_typed_decisions_v1.py (missing-response reconfirm, non-evidence
    research requests, incomplete ack coverage) and are not duplicated here.
    """

    def setUp(self):
        self.profile = runner.load_profile()

    def _ack_fixture(self):
        user = event("user-1", "stream-1", 1, "human_user", "human",
                     "Keep the requested behavior and preserve the constraints.", line=1)
        response = event("assistant-1", "stream-1", 2, "assistant_text", "agent",
                         "I will keep the requested behavior.", line=2)
        atom = runner._atomize(user.text, CharTokenizer(), 220, 32)[0]
        span_id = runner._span_id(user.event_id, atom)
        statuses = {span_id: {"status": "durable_assertion",
                              "ack_expectation": "required", "scored": True}}
        jobs, plans, _stats = runner._acknowledgment_jobs(
            "run", "profile", self.profile, user, [user, response],
            [atom], statuses, CharTokenizer())
        return jobs, plans

    @staticmethod
    def _strip_clock(rows):
        return json.dumps([
            {k: v for k, v in row.items()
             if k not in ("decision_receipt_time", "created_at")} for row in rows],
            sort_keys=True)

    def test_M16_partial_ack_reconfirms_and_identifies_response_span(self):
        jobs, plans = self._ack_fixture()
        for choice, (status, route) in (("accurate", ("accurate", "proceed")),
                                        ("partial", ("partial", "reconfirm_intent"))):
            results = {job["job_id"]: {"status": "scored", "answers": {
                "acknowledgment_response": {"choice": choice}}} for job in jobs}
            rows = runner._aggregate_phase2(
                jobs, results, plans, {}, {"stream-1": {"complete": True}})
            span = next(r for r in rows if r["record_type"] == "acknowledgment_gate_aggregate")
            self.assertEqual((span["status"], span["recommended_route"]), (status, route))
            self.assertTrue(all(detail["response_span_id"] and detail["response_char_span"]
                                for detail in span["decision_details"]))

    def test_M17_accurate_ack_does_not_authorize_conflicting_tool(self):
        ack_jobs, ack_plans = self._ack_fixture()
        ack_results = {job["job_id"]: {"status": "scored", "answers": {
            "acknowledgment_response": {"choice": "accurate"}}} for job in ack_jobs}
        tool_job = {"job_id": "tool-job", "meta": {
            "gate": "tool_pin_relation", "stream_id": "stream-1",
            "event_id": "tool-1", "run_id": "run", "pin_id": "pin-1"}}
        tool_result = {"status": "scored", "answers": {"tool_pin": {"choice": "conflict"}}}
        rows = runner._aggregate_phase2(
            ack_jobs + [tool_job], {**ack_results, "tool-job": tool_result},
            ack_plans, {"pin-1": {"status": "durable_assertion"}},
            {"stream-1": {"complete": True}})
        ack = next(r for r in rows if r["record_type"] == "acknowledgment_gate_aggregate")
        tool = next(r for r in rows if r["record_type"] == "tool_gate_aggregate")
        self.assertEqual((ack["status"], ack["recommended_route"]), ("accurate", "proceed"))
        self.assertEqual((tool["verdict"], tool["recommended_route"]),
                         ("deny", "rethink_plan"))

    def test_M24_only_the_conflicting_action_is_held(self):
        bad = {"job_id": "tool-bad", "meta": {
            "gate": "tool_pin_relation", "stream_id": "stream-1",
            "event_id": "tool-drop", "run_id": "run", "pin_id": "pin-1"}}
        good = {"job_id": "tool-ok", "meta": {
            "gate": "tool_pin_relation", "stream_id": "stream-1",
            "event_id": "tool-read", "run_id": "run", "pin_id": "pin-1"}}
        results = {"tool-bad": {"status": "scored",
                                "answers": {"tool_pin": {"choice": "conflict"}}},
                   "tool-ok": {"status": "scored",
                               "answers": {"tool_pin": {"choice": "consistent"}}}}
        rows = runner._aggregate_phase2([bad, good], results, [],
                                        {"pin-1": {"status": "durable_assertion"}},
                                        {"stream-1": {"complete": True}})
        by_event = {r["event_id"]: r for r in rows
                    if r["record_type"] == "tool_gate_aggregate"}
        self.assertEqual(by_event["tool-drop"]["recommended_route"], "rethink_plan")
        self.assertEqual(by_event["tool-read"]["recommended_route"], "proceed")

    def test_M11_missing_pin_result_cannot_yield_proceed(self):
        one = {"job_id": "tool-1j", "meta": {
            "gate": "tool_pin_relation", "stream_id": "stream-1",
            "event_id": "tool-1", "run_id": "run", "pin_id": "pin-1"}}
        two = {"job_id": "tool-2j", "meta": {
            "gate": "tool_pin_relation", "stream_id": "stream-1",
            "event_id": "tool-1", "run_id": "run", "pin_id": "pin-2"}}
        scored = {"tool-1j": {"status": "scored",
                              "answers": {"tool_pin": {"choice": "consistent"}}}}
        rows = runner._aggregate_phase2([one, two], scored, [],
                                        {"pin-1": {"status": "durable_assertion"},
                                         "pin-2": {"status": "durable_assertion"}},
                                        {"stream-1": {"complete": True}})
        tool = next(r for r in rows if r["record_type"] == "tool_gate_aggregate")
        self.assertEqual(tool["status"], "incomplete")
        self.assertNotEqual(tool["recommended_route"], "proceed")

    def test_M14_M23_non_supporting_evidence_cannot_silently_proceed(self):
        research = {"job_id": "res-1", "meta": {
            "gate": "research_evidence_relation", "stream_id": "stream-1",
            "event_id": "boundary-1", "run_id": "run",
            "claim_source_event_id": "claim-1", "claim_span": [0, 10],
            "evidence_event_id": "ev-1"}}
        plan = {"record_type": "research_gate_plan", "event_id": "boundary-1",
                "stream_sha256": runner._hash_id("stream-1"), "status": "planned",
                "planned_job_count": 1,
                "pack": {"claim_atoms": 1, "claim_events": ["claim-1"],
                         "claim_coverage": [{"claim_source_event_id": "claim-1",
                                             "claim_span": [0, 10]}],
                         "unmatched_claim_spans": []}}
        for choice in ("insufficient", "irrelevant", "contradicts",
                       "relevant_but_incomplete"):
            with self.subTest(choice=choice):
                result = {"status": "scored",
                          "answers": {"research_evidence": {"choice": choice}}}
                rows = runner._aggregate_phase2([research], {"res-1": result},
                                                [plan], {},
                                                {"stream-1": {"complete": True}})
                agg = next(r for r in rows if r["record_type"] == "research_gate_aggregate")
                self.assertNotEqual(agg["recommended_route"], "proceed")
                self.assertIn(agg["recommended_route"],
                              {"research_more", "dispatch_verifier", "escalate"})

    def test_M05_M21_later_or_moved_evidence_cannot_repair_earlier_claim(self):
        early_plan = {"record_type": "research_gate_plan", "event_id": "boundary-early",
                      "stream_sha256": runner._hash_id("stream-1"), "status": "planned",
                      "planned_job_count": 0,
                      "pack": {"claim_atoms": 1, "claim_events": ["claim-1"],
                               "claim_coverage": [],
                               "unmatched_claim_spans": [{
                                   "claim_source_event_id": "claim-1",
                                   "claim_span": [0, 12], "claim_timestamp":
                                       "2026-09-29T12:00:01Z"}]}}
        baseline = runner._aggregate_phase2([], {}, [early_plan], {},
                                           {"stream-1": {"complete": True}})
        early = next(r for r in baseline
                     if r["record_type"] == "research_gate_aggregate")
        self.assertEqual(early["recommended_route"], "dispatch_verifier")
        late_job = {"job_id": "res-late", "meta": {
            "gate": "research_evidence_relation", "stream_id": "stream-1",
            "event_id": "boundary-later", "run_id": "run",
            "claim_source_event_id": "claim-1", "claim_span": [0, 12],
            "evidence_event_id": "ev-after"}}
        late_plan = dict(early_plan, event_id="boundary-later", planned_job_count=1)
        scored = {"res-late": {"status": "scored",
                               "answers": {"research_evidence": {"choice": "supports"}}}}
        grown = runner._aggregate_phase2([late_job], scored, [early_plan, late_plan],
                                         {}, {"stream-1": {"complete": True}})
        grown_early = next(r for r in grown if r["record_type"] == "research_gate_aggregate"
                           and r["event_id"] == "boundary-early")
        self.assertEqual(self._strip_clock([grown_early]), self._strip_clock([early]))

    def test_M12_M26_reducer_output_is_order_and_worker_invariant(self):
        ack_jobs, ack_plans = self._ack_fixture()
        tool = {"job_id": "tool-j", "meta": {
            "gate": "tool_pin_relation", "stream_id": "stream-1",
            "event_id": "tool-1", "run_id": "run", "pin_id": "pin-1"}}
        results = {job["job_id"]: {"status": "scored", "answers": {
            "acknowledgment_response": {"choice": "accurate"}}} for job in ack_jobs}
        results["tool-j"] = {"status": "scored",
                             "answers": {"tool_pin": {"choice": "consistent"}}}
        pins = {"pin-1": {"status": "durable_assertion"}}
        quality = {"stream-1": {"complete": True}}
        jobs = ack_jobs + [tool]
        reference = self._strip_clock(
            runner._aggregate_phase2(jobs, results, ack_plans, pins, quality))
        rng = random.Random(0x5EED)
        for _ in range(5):
            shuffled = list(jobs)
            rng.shuffle(shuffled)
            perm_results = dict(reversed(list(results.items())))
            self.assertEqual(self._strip_clock(
                runner._aggregate_phase2(shuffled, perm_results, ack_plans, pins, quality)),
                reference)


class GeneratedFuzzTests(unittest.TestCase):
    """Deterministic seeded grammar fuzz over the protocol's axes."""

    SEED = 0xACE5

    def setUp(self):
        self.profile = runner.load_profile()

    def _stream(self, rng):
        topics = ["the export format", "the retry budget", "the audit window",
                  "the staging endpoint", "the rollback path"]
        qualifiers = ["", "never ", "only ", "always ", "not "]
        events = []
        for index in range(1, rng.randint(4, 9)):
            topic = rng.choice(topics)
            limit = rng.randint(2, 900)
            text = (f"{rng.choice(qualifiers)}Keep {topic} at {limit} "
                    f"{'attempts' if 'budget' in topic else 'units'}; "
                    f"{'do not widen' if rng.random() < 0.5 else 'preserve'} "
                    f"the existing {topic} contract.")
            events.append(event(f"fu-{index}", "stream-f", index, "human_user",
                                "human", text, line=index))
            if rng.random() < 0.4:
                events.append(event(f"fa-{index}", "stream-f", index, "assistant_text",
                                    "agent", f"Understood: {topic} stays fixed.",
                                    line=index))
            if rng.random() < 0.3:
                events.append(event(f"ft-{index}", "stream-f", index, "tool_call",
                                    "agent", json.dumps({"name": "read", "input": topic}),
                                    line=index, tool_name="read"))
        return events

    def test_fuzz_invariants(self):
        rng = random.Random(self.SEED)
        checked_pairs = 0
        for iteration in range(120):
            events = self._stream(rng)
            atoms, jobs, expected = build_user_jobs(events, self.profile)
            context = f"seed={hex(self.SEED)} iteration={iteration}"
            pin_ids = pin_job_ids(jobs)
            self.assertTrue(pin_ids, context)
            self.assertEqual(len(pin_ids), len(set(pin_ids)), context)
            for job in jobs:
                meta = job["meta"]
                self.assertTrue(meta["source_file_sha256"], context)
                self.assertGreater(meta["source_line"], 0, context)
                if meta["gate"] == "user_message_relation":
                    checked_pairs += 1
                    self.assertLessEqual(meta["prior_timestamp"],
                                         meta["current_timestamp"], context)
            rebuilt_ids = pin_job_ids(build_user_jobs(events, self.profile)[1])
            self.assertEqual(rebuilt_ids, pin_ids, context)
            if len(events) > 2:
                prefix = events[:-1]
                _, prefix_jobs, _ = build_user_jobs(prefix, self.profile)
                for job in prefix_jobs:
                    if job["meta"]["gate"] == "user_pin_status":
                        key = (job["meta"]["event_id"], job["job_id"])
                        self.assertEqual(job["request_hash"], pin_ids[key], context)
            ack_eligible = [job for job in jobs
                            if job["meta"]["gate"] == "user_pin_status"]
            statuses, _stats = runner._pin_statuses(
                ack_eligible, {job["job_id"]: scored_pin() for job in ack_eligible})
            self.assertEqual(len(statuses), len(ack_eligible), context)
            self.assertTrue(all("expir" not in key for status in statuses.values()
                                for key in status), context)
        self.assertGreater(checked_pairs, 50, "fuzz grammar degenerated to no pairs")


if __name__ == "__main__":
    unittest.main()
