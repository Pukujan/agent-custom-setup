from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import aggregate_research_receipts as aggregator


def receipt(*, choice="ready", status="scored_chunk", lane="lane-a", stream="a" * 64,
            event="tool-1:b0", event_kind="tool_call", evidence_ids=None, claim_chunk_index=0,
            source_hash="b" * 64, run="run-1"):
    return {
        "schema_version": 1, "run_id": run, "lane_id": lane, "model_id": "model-local",
        "stream_id_sha256": stream, "event_id": event, "event_kind": event_kind,
        "source_content_sha256": source_hash, "gate": "research", "status": status,
        "choice": choice, "evidence_ids": evidence_ids or ["read-1:b0"],
        "claim_chunk_index": claim_chunk_index,
        # Deliberately untrusted prose must never be copied to derived output.
        "private_test_text": "SYNTHETIC_SECRET_SENTINEL",
    }


class AggregateResearchReceiptTests(unittest.TestCase):
    def test_chunk_outcomes_follow_deterministic_order_and_emit_shadow_route(self):
        cases = [
            ([receipt(choice="ready"), receipt(choice="ready", claim_chunk_index=1)], "ready", "go"),
            ([receipt(choice="ready"), receipt(choice="research_more", claim_chunk_index=1)], "research_more", "loop"),
            ([receipt(choice="research_more"), receipt(choice="insufficient", claim_chunk_index=1)], "insufficient", "hold"),
        ]
        for rows, outcome, route in cases:
            with self.subTest(outcome=outcome):
                result, route_row = aggregator.aggregate_group(aggregator._group_key(rows[0]), rows)
                self.assertEqual(result["research_outcome"], outcome)
                self.assertEqual(route_row["route"], route)
                self.assertEqual(route_row["gate"], "research_route")
                self.assertTrue(route_row["shadow_only"])
                self.assertFalse(route_row["enforcement_applied"])

    def test_any_incomplete_chunk_forces_incomplete_hold_even_if_others_say_ready(self):
        rows = [
            receipt(choice="ready", evidence_ids=["read-1:b0"]),
            receipt(choice="research_more", status="incomplete", evidence_ids=[], claim_chunk_index=1),
        ]
        result, route = aggregator.aggregate_group(aggregator._group_key(rows[0]), rows)
        self.assertEqual(result["research_outcome"], "incomplete")
        self.assertEqual(result["incomplete_rows"], 1)
        self.assertEqual(route["route"], "hold")
        self.assertEqual(route["coverage_status"], "explicitly_incomplete")

    def test_groups_remain_isolated_by_lane_stream_and_run(self):
        rows = [
            receipt(lane="lane-a", stream="a" * 64, run="run-1"),
            receipt(lane="lane-b", stream="a" * 64, run="run-1"),
            receipt(lane="lane-a", stream="c" * 64, run="run-1"),
            receipt(lane="lane-a", stream="a" * 64, run="run-2"),
        ]
        with TemporaryDirectory(prefix="research-aggregate-") as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            output_dir = root / "derived"
            source_dir.mkdir()
            source = source_dir / "events.jsonl"
            source.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            source_before = source.read_bytes()
            output = output_dir / "aggregated.jsonl"
            derived = aggregator.aggregate_receipts([source])
            aggregator.write_aggregate([source], output, derived)
            self.assertEqual(source.read_bytes(), source_before)
            output_text = output.read_text(encoding="utf-8")
            self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", output_text)
            output_rows = [json.loads(line) for line in output_text.splitlines()]
            groups = [row for row in output_rows if row["gate"] == "research_outcome_aggregate"]
            routes = [row for row in output_rows if row["gate"] == "research_route"]
            self.assertEqual(len(groups), 4)
            self.assertEqual(len(routes), 4)
            self.assertEqual({row["lane_id"] for row in groups}, {"lane-a", "lane-b"})
            self.assertTrue(all(row["distinct_evidence_ids"] == 1 for row in groups))

    def test_human_research_outcome_has_no_coding_route(self):
        row = receipt(event_kind="human_user")
        result, route = aggregator.aggregate_group(aggregator._group_key(row), [row])
        self.assertEqual(result["research_outcome"], "ready")
        self.assertIsNone(route)

    def test_incomplete_or_invalid_choice_never_becomes_ready(self):
        rows = [receipt(choice="ready"), receipt(choice="unsupported", claim_chunk_index=1)]
        result, route = aggregator.aggregate_group(aggregator._group_key(rows[0]), rows)
        self.assertEqual(result["research_outcome"], "incomplete")
        self.assertEqual(result["invalid_choice_rows"], 1)
        self.assertEqual(route["route"], "hold")

    def test_output_cannot_be_written_in_source_receipt_directory(self):
        with TemporaryDirectory(prefix="research-aggregate-path-") as tmp:
            root = Path(tmp)
            source = root / "events.jsonl"
            source.write_text(json.dumps(receipt()), encoding="utf-8")
            rows = aggregator.aggregate_receipts([source])
            with self.assertRaisesRegex(aggregator.AggregateError, "outside_source_receipt_directories"):
                aggregator.write_aggregate([source], root / "derived.jsonl", rows)


if __name__ == "__main__":
    unittest.main()
