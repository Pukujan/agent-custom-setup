"""Report privacy and counting boundaries, with entirely synthetic receipts."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from blind_replay_report import aggregate_compaction, aggregate_experiments, aggregate_receipts, main, render_report


class AggregateReportTests(unittest.TestCase):
    def _write(self, root, rows):
        path = Path(root) / "events.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return path

    def _row(self, **values):
        return {"run_id": "synthetic-01", "lane_id": "laya-pc", "model_id": "laya-typed-decisions",
                "content_included": False, "gate": "user_pin", "status": "scored",
                "choice": "durable_assertion", **values}

    def test_untrusted_fields_and_event_identifiers_never_render(self):
        sensitive = "PRIVATE_SENTINEL_DO_NOT_EXPORT"
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, [self._row(text=sensitive, prompt=sensitive, reason=sensitive,
                gold=sensitive, event_id=sensitive, stream_id_sha256=sensitive,
                model_id="laya-" + sensitive, lane_id=sensitive),
                self._row(choice=sensitive, gate=sensitive)])
            result = aggregate_receipts([path])
            self.assertNotIn(sensitive, json.dumps(result))
            self.assertNotIn(sensitive, render_report(result))
            self.assertEqual(result["receipt_rows"], 2)

    def test_final_choices_count_separately_from_supporting_excerpts(self):
        with tempfile.TemporaryDirectory() as root:
            row = self._row()
            path = self._write(root, [row, row, self._row(gate="user_pin_chunk", elapsed_ms=7.5),
                self._row(gate="user_relation", status="aggregated", choice="same_topic"),
                self._row(gate="research", status="scored_empty", choice="research_more")])
            lane = aggregate_receipts([path])["lanes"][0]
            self.assertEqual(lane["rows"], 4)
            self.assertEqual(lane["choices"]["user_pin"]["durable_assertion"], 1)
            self.assertNotIn("user_pin_chunk", lane["choices"])
            self.assertEqual(lane["timed_checks"], 1)
            self.assertEqual(lane["latency_p50_ms"], 7.5)

    def test_missing_pin_coverage_is_counted_without_exposing_ids(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, [self._row(gate="tool", verdict="escalate", status="incomplete",
                expected_pin_ids=["private-pin-a", "private-pin-b"], pin_groups=[{"pin_ids": ["private-pin-a"]}]),
                self._row(gate="tool", verdict="allow", expected_pin_ids=["private-pin-a"],
                          pin_groups=[{"pin_ids": ["private-pin-a"]}])])
            result = aggregate_receipts([path])
            lane = result["lanes"][0]
            self.assertEqual(lane["pin_coverage_incomplete"], 1)
            self.assertEqual(lane["pin_coverage_complete"], 1)
            self.assertNotIn("private-pin", render_report(result))

    def test_mixed_runs_and_content_bearing_receipts_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, [self._row(), self._row(run_id="other-run")])
            with self.assertRaisesRegex(ValueError, "mixed_run_receipts"):
                aggregate_receipts([path])
            path = self._write(root, [self._row(content_included=True)])
            with self.assertRaisesRegex(ValueError, "content_free_receipt_required"):
                aggregate_receipts([path])

    def test_empty_artifact_does_not_claim_inference_or_result(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "new.html"
            self.assertEqual(main(["--out", str(output)]), 0)
            rendered = output.read_text(encoding="utf-8")
            self.assertIn("Not run", rendered)
            self.assertIn("No replay receipts yet", rendered)
            self.assertNotIn("<script", rendered)

    def test_summary_cannot_hide_missing_or_incomplete_receipts(self):
        summary = {"content_included": False, "status": "complete"}
        self.assertEqual(aggregate_receipts([], run_summary=summary)["status"], "not_run")
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, [self._row(status="incomplete")])
            self.assertEqual(aggregate_receipts([path], run_summary=summary)["status"], "incomplete")

    def test_probability_bands_reject_foreign_keys_and_invalid_distributions(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, [self._row(scores={"durable_assertion": .91, "unclear": .09}),
                self._row(scores={"PRIVATE_SCORE_LABEL": 1}),
                self._row(scores={"durable_assertion": 1.5}),
                self._row(scores={"durable_assertion": float("nan")})])
            result = aggregate_receipts([path])
            self.assertEqual(sum(result["lanes"][0]["answer_probability_bins"].values()), 1)
            self.assertNotIn("PRIVATE_SCORE_LABEL", render_report(result))

    def test_latest_logical_retry_counts_once_with_attempt_and_cache_counters(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, [
                self._row(event_id="private-event", elapsed_ms=40, choice="unclear", model_called=True),
                self._row(event_id="private-event", elapsed_ms=0, model_called=True, model_cache_hit=True),
                self._row(event_id="private-event", elapsed_ms=0, model_called=True, model_cache_hit=True)])
            lane = aggregate_receipts([path])["lanes"][0]
            self.assertEqual(lane["rows"], 1)
            self.assertEqual(lane["attempt_rows"], 3)
            self.assertEqual(lane["retry_rows"], 1)
            self.assertEqual(lane["exact_duplicate_rows"], 1)
            self.assertEqual(lane["model_attempts"], 1)
            self.assertEqual(lane["cache_attempts"], 1)
            self.assertEqual(lane["timed_checks"], 0)
            self.assertEqual(lane["cached_timed_checks"], 1)
            self.assertEqual(lane["choices"]["user_pin"], {"durable_assertion": 1})

    def test_logical_keys_keep_prior_pairs_and_chunk_indices_separate(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, [self._row(event_id="e", gate="user_relation_chunk",
                prior_event_id=prior, prior_chunk_index=chunk, current_chunk_index=0)
                for prior, chunk in (("a", 0), ("a", 1), ("b", 0))])
            self.assertEqual(aggregate_receipts([path])["receipt_rows"], 3)

    def test_research_outcomes_and_shadow_routes_use_their_actual_fields(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, [self._row(event_id="a", gate="research_outcome", outcome="research_more"),
                self._row(event_id="a", gate="research_route", route="loop", shadow_only=True, enforcement_applied=False),
                self._row(event_id="b", gate="research_route", route="hold", status="incomplete")])
            lane = aggregate_receipts([path])["lanes"][0]
            self.assertEqual(lane["choices"]["research_outcome"], {"research_more": 1})
            self.assertEqual(lane["choices"]["research_route"], {"loop": 1, "hold": 1})
            self.assertEqual(lane["incomplete_checks"], 1)

    def test_baseline_stream_scope_caveat_is_fixed_without_claiming_wrong_decisions(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, [self._row(event_id="synthetic-event")])
            rendered = render_report(aggregate_receipts([path]))
            self.assertIn("Baseline context uses conversation/root/sidechain stream IDs. Task-level context IDs are not implemented. A stream may contain multiple tasks, so exhaustive pair checks can include cross-task comparisons. This is a scope caveat; individual decision correctness remains unmeasured.", rendered)

    def test_evidence_metadata_can_be_supplied_without_becoming_renderer_verified(self):
        report = aggregate_experiments([], context={
            "holdout": {"status": "passed", "evidence_sha256": "a" * 64, "split_manifest_sha256": "b" * 64},
            "metamorphic": {"status": "passed", "evidence_sha256": "c" * 64, "passed": 14, "total": 14, "failed": 0}})
        self.assertEqual(report["validation"]["holdout"]["status"], "passed")
        self.assertEqual(report["validation"]["metamorphic"]["status"], "passed")
        rendered = render_report(report)
        self.assertIn("supplied evidence metadata", rendered)
        self.assertIn("renderer does not run validation", rendered)

    def test_exploratory_partition_is_content_free_and_cannot_claim_hidden_holdout(self):
        sentinel = "PRIVATE_PARTITION_SESSION_AND_LABEL"
        partition = {"timing": "post-inference / pre-analysis exploratory partition",
            "partition_manifest_sha256": "a" * 64, "source_manifest_sha256": "b" * 64,
            "root_sessions": 14, "development_root_sessions": 10, "exploratory_root_sessions": 4,
            "descendant_streams": 66, "session_ids": [sentinel], "label": sentinel, "reason": sentinel}
        report = aggregate_experiments([], context={"exploratory_partition": partition,
            "holdout": {"status": "passed", "evidence_sha256": "c" * 64, "split_manifest_sha256": "d" * 64}})
        self.assertEqual(report["validation"]["holdout"], {"status": "not_implemented"})
        self.assertEqual(report["exploratory_partition"]["exploratory_root_sessions"], 4)
        self.assertNotIn(sentinel, json.dumps(report))
        rendered = render_report(report)
        self.assertIn("post-inference / pre-analysis exploratory partition", rendered)
        self.assertIn("Hidden whole-session holdout: Not implemented", rendered)
        self.assertNotIn(sentinel, rendered)
        with self.assertRaisesRegex(ValueError, "timing_invalid"):
            aggregate_experiments([], context={"exploratory_partition": {**partition, "timing": "preregistered"}})
        with self.assertRaisesRegex(ValueError, "counts_invalid"):
            aggregate_experiments([], context={"exploratory_partition": {**partition, "root_sessions": 15}})

    def test_partition_streams_include_quarantine_and_reconcile_total(self):
        partition = {"timing": "post-inference / pre-analysis exploratory partition",
            "partition_manifest_sha256": "a" * 64, "root_sessions": 14,
            "development_root_sessions": 10, "exploratory_root_sessions": 4,
            "development_streams": 49, "exploratory_streams": 14, "quarantined_streams": 17,
            "total_streams": 80}
        report = aggregate_experiments([], context={"exploratory_partition": partition})
        self.assertEqual(report["exploratory_partition"]["quarantined_streams"], 17)
        self.assertEqual(report["exploratory_partition"]["total_streams"], 80)
        self.assertEqual(report["validation"]["holdout"]["status"], "not_implemented")
        self.assertIn("Quarantined streams", render_report(report))
        with self.assertRaisesRegex(ValueError, "stream_counts_mismatch"):
            aggregate_experiments([], context={"exploratory_partition": {**partition, "total_streams": 79}})
        with self.assertRaisesRegex(ValueError, "counts_invalid"):
            aggregate_experiments([], context={"exploratory_partition": {**partition, "quarantined_streams": -1}})
        with self.assertRaisesRegex(ValueError, "counts_invalid"):
            aggregate_experiments([], context={"exploratory_partition": {**partition, "quarantined_streams": True}})
        with self.assertRaisesRegex(ValueError, "stream_counts_incomplete"):
            aggregate_experiments([], context={"exploratory_partition": {key: value for key, value in partition.items()
                                                                        if key != "quarantined_streams"}})

    def test_auto_adapter_contract_and_unsupported_rows_are_visible(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(root, [self._row(adapter="auto-mode-openjev-local-v1", event_id="a",
                gate="auto_mode_tool", model_id="openjev-4b", decision="deny", probabilities={"deny": .9, "allow": .1},
                distribution_complete=True, latency_ms=20, model_called=True),
                self._row(adapter="auto-mode-openjev-local-v2", event_id="b", gate="auto_mode_tool",
                    model_id="openjev-4b", decision="allow", model_called=False),
                self._row(adapter="foreign-private-adapter", event_id="c"),
                self._row(event_id="d", gate="foreign-private-gate")])
            result = aggregate_receipts([path])
            auto = next(lane for lane in result["lanes"] if lane["adapter"] == "auto_mode")
            self.assertEqual(auto["choices"]["auto_mode_tool"], {"deny": 1, "allow": 1})
            self.assertEqual(auto["policy_bypasses"], 1)
            self.assertEqual(auto["latency_p50_ms"], 20)
            self.assertEqual(result["unsupported_rows"], 1)
            self.assertEqual(result["status"], "incomplete")
            rendered = render_report(result)
            self.assertIn("Unsupported gate rows", rendered)
            self.assertNotIn("foreign-private", rendered)

    def test_compaction_allowlist_never_exports_text_or_arbitrary_stats(self):
        sentinel = "PRIVATE_COMPACTION_SENTINEL"
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "compact.json"
            path.write_text(json.dumps({"adapter": "fast-jev-compaction-openjev-local", "content_included": False,
                "source_sha256": "a" * 64, "status": "complete", "model": {"name": "openjev-9b", "digest": "b" * 64},
                "content_preservation": {"unchanged": True, "text": sentinel}, "failure": sentinel,
                "compaction": {"stats": {"calls": 5, "kept": 3, "stateStage": sentinel, sentinel: 123},
                    "decision_action_counts": {"keep": 3, "drop_result": 2, sentinel: 12}, "openjev_requests": 10,
                    "openjev_latency_ms": {"median": 4, "p95": 8}}}), encoding="utf-8")
            result = aggregate_compaction([path, path])
            self.assertEqual(len(result["receipts"]), 1)
            self.assertEqual(result["exact_duplicate_rows"], 1)
            self.assertEqual(result["receipts"][0]["stats"], {"calls": 5, "kept": 3})
            report = aggregate_experiments([], result)
            self.assertNotIn(sentinel, json.dumps(report))
            self.assertNotIn(sentinel, render_report(report))
            self.assertIn("not replay at every historical boundary", render_report(report))

    def test_validation_and_missing_roster_defaults_and_evidence_boundaries(self):
        report = aggregate_experiments([])
        self.assertEqual(report["validation"]["holdout"]["status"], "not_implemented")
        self.assertEqual(report["validation"]["metamorphic"]["status"], "unverified")
        self.assertEqual(report["sources"][1]["status"], "missing")
        self.assertTrue(all(row["status"].startswith("Not run") for row in report["roster"]))
        report = aggregate_experiments([], context={
            "holdout": {"status": "passed", "evidence_sha256": "a" * 64},
            "metamorphic": {"status": "passed", "evidence_sha256": "b" * 64, "passed": 7, "total": 14, "failed": 0}})
        self.assertEqual(report["validation"]["holdout"]["status"], "unverified")
        self.assertEqual(report["validation"]["metamorphic"]["status"], "unverified")

    def test_separate_run_directories_and_compaction_inputs_via_cli(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            first, second = base / "first" / "lane", base / "second" / "lane"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            (first / "events.jsonl").write_text(json.dumps(self._row(event_id="a")) + "\n", encoding="utf-8")
            (second / "events.jsonl").write_text(json.dumps(self._row(run_id="synthetic-02", event_id="b",
                adapter="auto-mode-openjev-local-v1", gate="auto_mode_tool", decision="deny")) + "\n", encoding="utf-8")
            compactor = base / "compactor.json"
            compactor.write_text(json.dumps({"content_included": False, "adapter": "fast-jev-compaction-openjev-local",
                                           "status": "planned"}), encoding="utf-8")
            output = base / "combined.html"
            self.assertEqual(main(["--receipt-dir", str(first.parent), "--receipt-dir", str(second.parent),
                                   "--compaction-receipt", str(compactor), "--out", str(output)]), 0)
            rendered = output.read_text(encoding="utf-8")
            for label in ("Baseline walk-forward", "Auto-mode tool adapter", "Fast-jev-compaction adapter"):
                self.assertIn(label, rendered)
            self.assertNotIn("synthetic-01", rendered)
            self.assertNotIn("synthetic-02", rendered)


if __name__ == "__main__":
    unittest.main()
