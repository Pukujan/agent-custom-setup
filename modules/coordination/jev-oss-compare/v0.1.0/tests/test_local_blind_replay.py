from __future__ import annotations

import json
import contextlib
import io
import sys
import threading
import unittest
from argparse import Namespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from local_decision_client import LocalDecisionClient, LocalEndpointError, LocalModelConfig
from openjev_ollama_client import OpenJevOllamaClient, OllamaOpenJevConfig
import local_blind_replay as runner
from replay_core import all_prior_user_pairs, compact_retention, hard_deny_reason, prefix_before, public_evidence_ledger
from replay_sources import SourceIntegrityError, SourceReport, link_sidechains, normalize_claude_rows, public_summary


class ParserTests(unittest.TestCase):
    def test_role_authority_and_tool_result_are_distinct(self) -> None:
        rows = [
            (1, {"type": "user", "uuid": "u1", "sessionId": "s", "message": {"role": "user", "content": "please use the documented API"}}),
            (2, {"type": "user", "uuid": "r1", "sessionId": "s", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "API docs text"}]}}),
            (3, {"type": "user", "uuid": "u2", "sessionId": "s", "isSidechain": True, "agentId": "a1", "message": {"role": "user", "content": "delegated instructions"}}),
        ]
        events = normalize_claude_rows(rows)
        self.assertEqual([e.kind for e in events], ["human_user", "tool_result", "delegated_prompt"])
        self.assertEqual([e.authority for e in events], ["human", "tool", "agent"])
        self.assertNotEqual(events[0].stream_id, events[2].stream_id)

    def test_claude_meta_user_envelopes_are_not_human_intent(self) -> None:
        rows = [(1, {"type": "user", "uuid": "meta", "sessionId": "s", "isMeta": True,
                     "message": {"role": "user", "content": "<local-command-stdout>"}})]
        event = normalize_claude_rows(rows)[0]
        self.assertEqual((event.kind, event.authority), ("meta_user", "system"))

    def test_duplicate_uuid_collapses_and_conflicting_uuid_fails_closed(self) -> None:
        base = {"type": "user", "uuid": "same", "sessionId": "s", "message": {"role": "user", "content": "one"}}
        report = SourceReport()
        events = normalize_claude_rows([(1, base), (2, dict(base))], report=report)
        self.assertEqual(len(events), 1)
        self.assertEqual(report.duplicate_rows, 1)
        changed = {**base, "message": {"role": "user", "content": "different"}}
        with self.assertRaisesRegex(SourceIntegrityError, "conflicting_source_uuid"):
            normalize_claude_rows([(3, base), (4, changed)])

    def test_session_bookkeeping_changes_do_not_turn_duplicate_into_conflict(self) -> None:
        base = {"type": "user", "uuid": "same", "sessionId": "s", "message": {"role": "user", "content": "one"}, "origin": "a", "promptId": "p1"}
        changed_metadata = {**base, "origin": "b", "promptId": "p2"}
        report = SourceReport()
        events = normalize_claude_rows([(1, base), (2, changed_metadata)], report=report)
        self.assertEqual(len(events), 1)
        self.assertEqual(report.duplicate_rows, 1)
        self.assertEqual(report.duplicate_sources[0]["line"], 2)

    def test_compact_boundary_preserves_metadata_but_public_summary_does_not_leak(self) -> None:
        rows = [(4, {"type": "system", "subtype": "compact_boundary", "uuid": "c1", "sessionId": "s", "content": "summary text", "compactMetadata": {"preservedMessages": ["m1"], "trigger": "auto"}})]
        events = normalize_claude_rows(rows)
        self.assertEqual(events[0].kind, "compact_boundary")
        self.assertIn("preservedMessages", events[0].metadata)
        summary = public_summary(events, SourceReport(files=1, rows=1))
        self.assertNotIn("summary text", json.dumps(summary))

    def test_sidechain_links_only_to_unique_parent_agent_tool_call(self) -> None:
        rows = [
            (1, {"type": "assistant", "uuid": "spawn-row", "sessionId": "s", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "agent-call", "name": "Agent", "input": {"prompt": "delegate"}}]}}),
            (1, {"type": "user", "uuid": "child-start", "sessionId": "s", "isSidechain": True, "agentId": "agent-a", "parentUuid": "spawn-row", "message": {"role": "user", "content": "delegate"}}),
        ]
        events = normalize_claude_rows(rows)
        link_sidechains(events)
        child = next(event for event in events if event.kind == "delegated_prompt")
        self.assertEqual(child.metadata["delegation_link_status"], "resolved")
        self.assertEqual(child.metadata["delegated_from_event_id"], "spawn-row:b0")

    def test_same_uuid_delegated_prompt_is_preserved_per_agent_stream(self) -> None:
        rows = [
            (1, {"type": "user", "uuid": "shared", "sessionId": "s", "isSidechain": True, "agentId": agent, "message": {"role": "user", "content": "same delegated task"}})
            for agent in ("agent-a", "agent-b")
        ]
        events = normalize_claude_rows(rows)
        self.assertEqual(len(events), 2)
        self.assertEqual(len({event.stream_id for event in events}), 2)
        self.assertEqual(len({event.event_id for event in events}), 2)


class ReplayCoreTests(unittest.TestCase):
    def _events(self):
        rows = [
            (1, {"type": "user", "uuid": "u1", "sessionId": "s", "message": {"role": "user", "content": "first"}}),
            (2, {"type": "assistant", "uuid": "a1", "sessionId": "s", "parentUuid": "u1", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "tool1", "name": "WebFetch", "input": {"url": "https://docs.example/api"}}]}}),
            (3, {"type": "user", "uuid": "r1", "sessionId": "s", "parentUuid": "a1", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tool1", "content": "versioned docs"}]}}),
            (4, {"type": "user", "uuid": "u2", "sessionId": "s", "message": {"role": "user", "content": "second"}}),
        ]
        return normalize_claude_rows(rows)

    def test_each_human_message_compares_with_every_prior_human_message(self) -> None:
        pairs = all_prior_user_pairs(self._events())
        self.assertEqual(len(pairs), 1)
        self.assertEqual((pairs[0].prior_event_id, pairs[0].current_event_id), ("u1:b0", "u2:b0"))

    def test_research_ledger_is_as_of_prefix_only(self) -> None:
        events = self._events()
        before_tool_result = public_evidence_ledger(prefix_before(events, 2))
        after_tool_result = public_evidence_ledger(prefix_before(events, 3))
        self.assertEqual(before_tool_result, [])
        self.assertEqual(len(after_tool_result), 1)
        self.assertEqual(after_tool_result[0]["tool_name"], "WebFetch")

    def test_hard_deny_extracts_shell_command_from_historic_tool_payload(self) -> None:
        rows = [(1, {"type": "assistant", "uuid": "a", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": "Bash", "input": {"command": "rm -rf /"}}]}})]
        event = normalize_claude_rows(rows)[0]
        self.assertEqual(hard_deny_reason(event), "catastrophic_shell_pattern")

    def test_hard_deny_is_not_applied_to_non_shell_tools(self) -> None:
        rows = [(1, {"type": "assistant", "uuid": "a", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t", "name": "Read", "input": {"file_path": "rm -rf /"}}]}})]
        event = normalize_claude_rows(rows)[0]
        self.assertIsNone(hard_deny_reason(event))

    def test_compaction_uses_captured_ids_but_does_not_claim_semantic_loss(self) -> None:
        row = {"type": "system", "subtype": "compact_boundary", "uuid": "c", "compactMetadata": {"preservedMessages": {"allUuids": ["kept"], "uuids": ["kept"]}}}
        boundary = normalize_claude_rows([(1, row)])[0]
        kept = compact_retention(boundary, "kept:b0")
        omitted = compact_retention(boundary, "omitted:b0")
        self.assertEqual(kept["source_id_status"], "preserved")
        self.assertEqual(omitted["source_id_status"], "not_preserved_by_id")
        self.assertEqual(omitted["semantic_status"], "unknown")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = {"data": [{"id": "local-test-model", "revision": "rev-1", "device": "cpu"}]}
        self._reply(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.server.last_payload = json.loads(self.rfile.read(length).decode())  # type: ignore[attr-defined]
        self._reply({"model": "local-test-model", "answers": {"q": {"choice": "yes", "probabilities": {"yes": 0.8, "no": 0.2}, "answer_confidence": 0.8}}})

    def _reply(self, value: Any) -> None:
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        return


class _OpenJevHandler(_Handler):
    def do_GET(self) -> None:
        if self.path == "/api/tags":
            self._reply({"models": [{"name": "hf.co/apus-ailab/APUS-OpenJev-v1-4B-GGUF:Q4_K_M", "size": 123}]})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.server.last_payload = json.loads(self.rfile.read(length).decode())  # type: ignore[attr-defined]
        self._reply({"response": "A", "logprobs": [{"top_logprobs": [{"token": "A", "logprob": -0.1}, {"token": "B", "logprob": -1.1}]}]})


class LocalClientTests(unittest.TestCase):
    def test_rejects_nonlocal_or_unlisted_hosts(self) -> None:
        for url in ("https://127.0.0.1:8000", "http://example.com:8000", "http://100.79.248.88:8000"):
            with self.subTest(url=url), self.assertRaises(LocalEndpointError):
                LocalDecisionClient(LocalModelConfig("lane", url, "model"))
        # A tailnet address is allowed only when the exact IP is pinned.
        client = LocalDecisionClient(LocalModelConfig("lane", "http://100.79.248.88:8000", "model", allow_tailnet_ips=["100.79.248.88"]))
        self.assertIsNotNone(client)

    def test_reads_inventory_and_posts_typed_decision(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        server.last_payload = None
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            client = LocalDecisionClient(LocalModelConfig("lane-a", f"http://127.0.0.1:{port}", "local-test-model", expected_revision="rev-1"))
            inventory = client.inventory()
            self.assertEqual(inventory["selected"]["id"], "local-test-model")
            result = client.decide(state={"text": "hello"}, questions={"q": {"type": "choice", "instructions": "choose", "criteria": {"yes": "yes", "no": "no"}}})
            self.assertEqual(result["answers"]["q"]["choice"], "yes")
            self.assertEqual(server.last_payload["model"], "local-test-model")
            self.assertEqual(result["confidence_definition"], "provider_defined; record raw fields")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()


class RunnerTests(unittest.TestCase):
    def test_text_chunking_preserves_every_character_and_conservative_aggregation(self) -> None:
        source = "alpha beta\ngamma delta\n" * 17
        chunks = runner._text_chunks(source, 19)
        self.assertEqual("".join(piece for _, _, piece in chunks), source)
        self.assertEqual(chunks[0][0], 0)
        self.assertEqual(chunks[-1][1], len(source))
        self.assertEqual(runner._aggregate_unanimous(["same_topic", "same_topic"]), "same_topic")
        self.assertEqual(runner._aggregate_unanimous(["same_topic", "revises_or_supersedes"]), "unclear")
        self.assertEqual(runner._aggregate_tool_chunks(["consistent", "conflict"]), "conflict")

    def test_mocked_walkforward_run_writes_only_content_free_receipts(self) -> None:
        class FakeClient:
            def __init__(self, group_choice="allow"):
                self.group_choice = group_choice

            def inventory(self):
                return {"selected": {"id": "fake", "revision": "rev-test"}}

            def decide(self, *, state, questions):
                question = questions["decision"]
                criteria = question["criteria"]
                if "prior_user_message_chunk" in state:
                    choice = "revises_or_supersedes" if "Actually" in state["current_user_message_chunk"] else "unrelated"
                elif "current_user_message_chunk" in state:
                    choice = "durable_assertion"
                elif "active_pins" in state:
                    choice = self.group_choice
                elif "pinned_user_message_excerpt" in state:
                    choice = "conflict" if state["pin_hard_constraint"] else "consistent"
                elif "pinned_user_message_chunk" in state:
                    choice = "consistent"
                elif "claim" in state:
                    choice = "ready"
                else:
                    raise AssertionError("unexpected model state")
                return {"model": "fake", "answers": {"decision": {
                    "choice": choice,
                    "probabilities": {key: (1.0 if key == choice else 0.0) for key in criteria},
                    "answer_confidence": 1.0,
                }}}

        with TemporaryDirectory(prefix="replay-test-") as tmp:
            root = Path(tmp) / "raw"
            root.mkdir()
            rows = [
                {"type": "user", "uuid": "u1", "sessionId": "s", "timestamp": "2026-01-01T00:00:00Z", "message": {"role": "user", "content": "Keep generated artifacts in SQLite."}},
                {"type": "assistant", "uuid": "a1", "sessionId": "s", "timestamp": "2026-01-01T00:00:01Z", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "docs.md"}}]}},
                {"type": "user", "uuid": "r1", "sessionId": "s", "timestamp": "2026-01-01T00:00:02Z", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "Versioned SQLite reference material."}]}},
                {"type": "user", "uuid": "u2", "sessionId": "s", "timestamp": "2026-01-01T00:00:03Z", "message": {"role": "user", "content": "Actually, first compare whether SQLite is needed."}},
                {"type": "assistant", "uuid": "a2", "sessionId": "s", "timestamp": "2026-01-01T00:00:04Z", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "t2", "name": "Write", "input": {"file_path": "out.txt", "content": "data"}}]}},
                {"type": "system", "subtype": "compact_boundary", "uuid": "c1", "sessionId": "s", "timestamp": "2026-01-01T00:00:05Z", "compactMetadata": {"preservedMessages": {"allUuids": ["u2"]}}},
            ]
            (root / "session.jsonl").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1, "lanes": [{
                "lane_id": "fake", "backend": "systemone", "base_url": "http://127.0.0.1:9",
                "model_id": "fake", "expected_revision": "rev-test",
            }]}), encoding="utf-8")
            receipt_dir = Path(tmp) / "receipts"
            args = Namespace(source=str(root), manifest=str(manifest), run_id="synthetic-test",
                             receipt_dir=str(receipt_dir), dry_run_plan=False, execute_local=True)
            output = io.StringIO()
            with patch.object(runner, "_make_client", return_value=(FakeClient(), "systemone")), contextlib.redirect_stdout(output):
                status = runner.command_run(args)
            self.assertEqual(status, 0, output.getvalue())
            receipt = receipt_dir / "synthetic-test" / "fake" / "events.jsonl"
            data = receipt.read_text(encoding="utf-8")
            self.assertIn('"gate":"user_relation"', data)
            self.assertIn('"gate":"research"', data)
            self.assertIn('"gate":"research_outcome"', data)
            self.assertIn('"gate":"research_route"', data)
            self.assertIn('"gate":"tool"', data)
            self.assertIn('"gate":"tool_pin_group"', data)
            self.assertIn('"gate":"compaction"', data)
            self.assertNotIn("Keep generated artifacts", data)
            self.assertNotIn("Versioned SQLite", data)
            self.assertTrue(all(json.loads(line)["content_included"] is False for line in data.splitlines()))
            receipt_rows = [json.loads(line) for line in data.splitlines()]
            self.assertTrue(all(row["schema_version"] == 2 for row in receipt_rows))
            coding_routes = [row for row in receipt_rows
                             if row["gate"] == "research_route" and row["event_id"] == "a2:b0"]
            self.assertEqual(len(coding_routes), 1)
            self.assertEqual(coding_routes[0]["research_outcome"], "ready")
            self.assertEqual(coding_routes[0]["route"], "go")
            self.assertEqual(coding_routes[0]["shadow_permission"], "would_allow_coding")
            self.assertTrue(coding_routes[0]["shadow_only"])
            self.assertFalse(coding_routes[0]["enforcement_applied"])
            receipt_count = len(data.splitlines())
            output = io.StringIO()
            with patch.object(runner, "_make_client", return_value=(FakeClient(), "systemone")), contextlib.redirect_stdout(output):
                status = runner.command_run(args)
            rerun = json.loads(output.getvalue())
            self.assertEqual(status, 0)
            self.assertFalse(rerun["lane_results"][0]["inference_called"])
            self.assertGreater(rerun["lane_results"][0]["cache_hits"], 0)
            self.assertEqual(len(receipt.read_text(encoding="utf-8").splitlines()), receipt_count)

            args.run_id = "synthetic-deny"
            output = io.StringIO()
            with patch.object(runner, "_make_client", return_value=(FakeClient("deny"), "systemone")), contextlib.redirect_stdout(output):
                status = runner.command_run(args)
            self.assertEqual(status, 0, output.getvalue())
            deny_receipt = receipt_dir / "synthetic-deny" / "fake" / "events.jsonl"
            deny_data = deny_receipt.read_text(encoding="utf-8")
            self.assertIn('"gate":"tool_pin_diagnostic"', deny_data)
            self.assertIn('"verdict":"deny"', deny_data)

    def test_shadow_research_routes_cover_all_outcomes_without_enforcement(self) -> None:
        expected = {
            "ready": ("go", "would_allow_coding"),
            "research_more": ("loop", "would_hold_for_more_research"),
            "insufficient": ("hold", "would_hold_for_escalation"),
            "incomplete": ("hold", "would_hold_for_incomplete_evidence"),
        }
        for outcome, (route, permission) in expected.items():
            with self.subTest(outcome=outcome), TemporaryDirectory(prefix="research-route-") as tmp:
                event = normalize_claude_rows([
                    (1, {"type": "assistant", "uuid": "boundary", "sessionId": "route-test",
                         "message": {"role": "assistant", "content": [{"type": "tool_use",
                             "id": "write-1", "name": "Write", "input": {"file_path": "x"}}]}})
                ])[0]
                receipt = Path(tmp) / "events.jsonl"
                lane = {"lane_id": "fake", "model_id": "fake"}
                observation = runner._record_research_outcome(
                    receipt, "synthetic-route", lane, event.stream_id, event, outcome)
                runner._record_research_route(receipt, "synthetic-route", lane,
                                              event.stream_id, event, observation)
                rows = [json.loads(line) for line in receipt.read_text(encoding="utf-8").splitlines()]
                outcome_row, route_row = rows
                self.assertEqual(outcome_row["gate"], "research_outcome")
                self.assertEqual(outcome_row["outcome"], outcome)
                self.assertEqual(route_row["gate"], "research_route")
                self.assertEqual(route_row["route"], route)
                self.assertEqual(route_row["shadow_permission"], permission)
                self.assertTrue(route_row["shadow_only"])
                self.assertFalse(route_row["enforcement_applied"])

    def test_incomplete_asof_evidence_persists_hold_route_without_model_call(self) -> None:
        events = normalize_claude_rows([
            (1, {"type": "user", "uuid": "u1", "sessionId": "incomplete-test",
                 "message": {"role": "user", "content": "Check the API docs."}}),
            (2, {"type": "assistant", "uuid": "a1", "sessionId": "incomplete-test",
                 "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "read-1",
                     "name": "Read", "input": {"file_path": "docs.md"}}]}}),
            (3, {"type": "user", "uuid": "r1", "sessionId": "incomplete-test",
                 "message": {"role": "user", "content": [{"type": "tool_result",
                     "tool_use_id": "read-1", "content": "versioned official API reference evidence"}]}}),
            (4, {"type": "assistant", "uuid": "a2", "sessionId": "incomplete-test",
                 "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "write-1",
                     "name": "Write", "input": {"file_path": "implementation.py"}}]}}),
        ])
        boundary = next(event for event in events if event.kind == "tool_call" and event.tool_use_id == "write-1")
        user = next(event for event in events if event.kind == "human_user")
        with TemporaryDirectory(prefix="research-incomplete-") as tmp:
            receipt = Path(tmp) / "events.jsonl"
            lane = {"lane_id": "fake", "model_id": "fake"}
            outcome, calls = runner._research_gate(
                client=None, backend="systemone", lane=lane, stream_id=boundary.stream_id,
                event=boundary, events=events, receipt=receipt, run_id="synthetic-incomplete",
                claim="code against documented API", chunk_chars=1, max_chunks=1,
                max_input_chars=1000, max_chunk_pairs=16,
            )
            self.assertIsNone(outcome)
            self.assertEqual(calls, 0)
            observation = runner._record_research_outcome(
                receipt, "synthetic-incomplete", lane, boundary.stream_id, boundary, outcome)
            runner._record_research_route(receipt, "synthetic-incomplete", lane,
                                          boundary.stream_id, boundary, observation)
            rows = [json.loads(line) for line in receipt.read_text(encoding="utf-8").splitlines()]
            self.assertIn("omitted_evidence_ids", rows[0])
            self.assertEqual(rows[1]["gate"], "research_outcome")
            self.assertEqual(rows[1]["outcome"], "incomplete")
            self.assertEqual(rows[2]["gate"], "research_route")
            self.assertEqual(rows[2]["route"], "hold")
            self.assertFalse(rows[2]["enforcement_applied"])

        # A hold is only a shadow observation. It does not mutate the reducer
        # or alter the independent tool-gate result.
        state = runner.StreamState(boundary.stream_id)
        state.apply_human_decision(user, {"pin_status": "durable_assertion",
                                          "relations": {}, "supersedes": []})
        work = state.tool_pin_work(boundary)
        self.assertEqual(len(work), 1)
        verdict, _ = state.validate_tool_decision(
            {"verdict": "allow", "pins": {user.event_id: "consistent"}},
            [item.pin_event_id for item in work],
        )
        self.assertEqual(verdict, "allow")

    def test_kev_inventory_uses_name_run_and_base_identity(self) -> None:
        class KevHandler(_Handler):
            def do_GET(self) -> None:
                self._reply({"models": [{
                    "name": "kev-latest",
                    "run": "jaredpalmer/kev-0.8b@revision-abc",
                    "base": "Qwen/Qwen3.5-0.8B-Base",
                    "device": "cpu",
                    "dtype": "float32",
                }]})

        server = ThreadingHTTPServer(("127.0.0.1", 0), KevHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            client = LocalDecisionClient(LocalModelConfig(
                "kev-0.8b", f"http://127.0.0.1:{port}", "kev-latest",
                expected_revision="jaredpalmer/kev-0.8b@revision-abc",
                expected_base="Qwen/Qwen3.5-0.8B-Base",
            ))
            row = client.inventory()["selected"]
            self.assertEqual(row["revision"], "jaredpalmer/kev-0.8b@revision-abc")
            self.assertEqual(row["base"], "Qwen/Qwen3.5-0.8B-Base")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def test_openjev_uses_exact_local_candidate_contract_and_keeps_top20_limits(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _OpenJevHandler)
        server.last_payload = None
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            model = "hf.co/apus-ailab/APUS-OpenJev-v1-4B-GGUF:Q4_K_M"
            client = OpenJevOllamaClient(OllamaOpenJevConfig("openjev-4b", f"http://127.0.0.1:{port}", model))
            self.assertEqual(client.inventory()["selected"]["name"], model)
            result = client.decide(
                state="new user message",
                instructions="Choose the relation.",
                criteria=[{"id": "unrelated", "description": "No relation."}, {"id": "supersedes", "description": "Replaces prior intent."}],
            )
            self.assertTrue(result["distribution_complete"])
            self.assertEqual(result["answer"], "unrelated")
            self.assertAlmostEqual(result["probabilities"]["unrelated"] + result["probabilities"]["supersedes"], 1.0)
            self.assertTrue(server.last_payload["raw"])
            self.assertFalse(server.last_payload["think"])
            self.assertIn("Return only the selected letter: A, B.", server.last_payload["prompt"])
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def test_openjev_marks_missing_candidate_logits_incomplete(self) -> None:
        class MissingCandidateHandler(_OpenJevHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(length)
                self._reply({"response": "A", "logprobs": [{"top_logprobs": [{"token": "A", "logprob": -0.1}]}]})

        server = ThreadingHTTPServer(("127.0.0.1", 0), MissingCandidateHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            client = OpenJevOllamaClient(OllamaOpenJevConfig("openjev-4b", f"http://127.0.0.1:{port}", "hf.co/apus-ailab/APUS-OpenJev-v1-4B-GGUF:Q4_K_M"))
            result = client.decide(state="x", instructions="Choose.", criteria=[{"id": "one", "description": "One."}, {"id": "two", "description": "Two."}])
            self.assertFalse(result["distribution_complete"])
            self.assertNotIn("probabilities", result)
            self.assertEqual(result["distribution_omission_count"], 1)
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
