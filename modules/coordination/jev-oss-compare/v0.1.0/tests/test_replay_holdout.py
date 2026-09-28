"""Synthetic invariants for metadata-only exploratory session partitioning."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import replay_holdout as selector


def stream(identifier: str, *, parent: str | None = None,
           sidechain: bool = False, status: str | None = None,
           count: int = 3) -> dict:
    return {"stream_id": identifier, "is_sidechain": sidechain,
            "parent_stream_id": parent,
            "delegation_link_status": status or ("resolved" if sidechain else "root"),
            "event_count": count, "events_by_kind": {"tool_call": count}}


def inventory(*streams: dict) -> dict:
    return {"schema_version": 1, "source_hashes": {"a" * 16: "b" * 64},
            "streams": list(streams)}


def assignments(partition: dict) -> dict:
    return {group["root_stream_id_hash"]: group["partition"]
            for group in partition["root_groups"]}


class ExploratoryPartitionTests(unittest.TestCase):
    def test_whole_roots_keep_nested_resolved_descendants(self) -> None:
        source = inventory(stream("root-private-a"), stream("root-private-b"),
                           stream("child-private", sidechain=True, parent="root-private-a"),
                           stream("grandchild-private", sidechain=True, parent="child-private"))
        original = copy.deepcopy(source)
        result = selector.build_partition(source)
        group = next(item for item in result["root_groups"] if item["streams"] == 3)
        self.assertEqual(group["events"], 9)
        self.assertEqual(result["root_count"], 2)
        self.assertEqual(result["reserved_root_count"], 1)
        self.assertEqual(result["unresolved_ancestry_counts"]["streams"], 0)
        self.assertEqual(source, original)
        rendered = json.dumps(result)
        for name in ("root-private-a", "root-private-b", "child-private", "grandchild-private"):
            self.assertNotIn(name, rendered)
        for item in result["root_groups"]:
            self.assertEqual(len(item["root_stream_id_hash"]), 64)
            self.assertTrue(all(len(value) == 64 for value in item["stream_id_hashes"]))

    def test_selection_ignores_order_counts_and_source_content_hashes(self) -> None:
        source = inventory(*(stream(f"root-{index}", count=index + 1) for index in range(14)))
        baseline = selector.build_partition(source)
        changed = copy.deepcopy(source)
        changed["streams"].reverse()
        for item in changed["streams"]:
            item["event_count"] += 100
            item["events_by_kind"]["tool_call"] += 100
        changed["source_hashes"] = {"c" * 16: "d" * 64}
        updated = selector.build_partition(changed)
        self.assertEqual(assignments(baseline), assignments(updated))
        self.assertEqual(baseline["reserved_root_count"], 4)
        self.assertNotEqual(baseline["source_manifest_hash"], updated["source_manifest_hash"])
        reordered = copy.deepcopy(source)
        reordered["streams"].reverse()
        self.assertEqual(baseline, selector.build_partition(reordered))

    def test_uncertain_and_cyclic_ancestry_never_count_as_clean_partition(self) -> None:
        source = inventory(
            stream("root"),
            stream("lost", sidechain=True, status="unresolved"),
            stream("ambiguous", sidechain=True, parent="root", status="ambiguous"),
            stream("below-lost", sidechain=True, parent="lost"),
            stream("missing", sidechain=True, parent="not-in-corpus"),
            stream("null-parent", sidechain=True),
            stream("cycle-a", sidechain=True, parent="cycle-b"),
            stream("cycle-b", sidechain=True, parent="cycle-a"),
        )
        result = selector.build_partition(source)
        self.assertEqual(result["root_groups"][0]["streams"], 1)
        self.assertEqual(result["unresolved_ancestry_counts"],
                         {"streams": 7, "events": 21, "events_by_kind": {"tool_call": 21}})
        self.assertEqual(sum(item["streams"] for item in result["partition_counts"].values()), 1)
        reasons = [row["ancestry_status"] for row in result["unresolved_ancestry"]]
        self.assertEqual(reasons.count("ancestry_cycle"), 2)
        self.assertEqual(reasons.count("unresolved_ancestry"), 2)
        self.assertIn("ambiguous_ancestry", reasons)
        self.assertIn("parent_stream_missing", reasons)
        self.assertIn("resolved_link_missing_parent", reasons)

    def test_explicitly_exploratory_and_no_passed_holdout_claim(self) -> None:
        result = selector.build_partition(inventory(stream("root")))
        self.assertEqual(result["timing_label"], "post-inference / pre-analysis exploratory partition")
        self.assertFalse(result["preregistered_holdout"])
        self.assertFalse(result["holdout_benchmark_passed"])
        self.assertFalse(result["content_included"])
        unsigned = {key: value for key, value in result.items() if key != "selection_hash"}
        self.assertEqual(result["selection_hash"], selector._sha256(unsigned))

    def test_schema_rejects_content_decisions_and_raw_path_locators(self) -> None:
        source = inventory(stream("root"))
        variants = []
        changed = copy.deepcopy(source); changed["text"] = "private content"; variants.append(changed)
        changed = copy.deepcopy(source); changed["streams"][0]["decision"] = "allow"; variants.append(changed)
        changed = copy.deepcopy(source); changed["source_hashes"] = {"C:/raw/session.jsonl": "b" * 64}; variants.append(changed)
        changed = copy.deepcopy(source); changed["streams"][0]["event_count"] = 99; variants.append(changed)
        changed = copy.deepcopy(source); changed["streams"].append(stream("root")); variants.append(changed)
        changed = copy.deepcopy(source); changed["streams"][0]["events_by_kind"] = {"gold_decision": 3}; variants.append(changed)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(selector.PartitionError):
                selector.build_partition(value)
        for fraction in ("nan", "inf", "0", "1", "-0.25", "invalid"):
            with self.subTest(fraction=fraction), self.assertRaises(selector.PartitionError):
                selector.build_partition(source, holdout_fraction=fraction)

    def test_destination_outside_checkout_and_freeze_is_write_once(self) -> None:
        with TemporaryDirectory(prefix="holdout-private-") as tmp:
            outer = Path(tmp).resolve()
            checkout = outer / "checkout"; checkout.mkdir()
            result = selector.build_partition(inventory(stream("root")))
            with self.assertRaisesRegex(selector.PartitionError, "outside_checkout"):
                selector.write_private_partition(result, checkout / "private.json", checkout_root=checkout)
            with self.assertRaisesRegex(selector.PartitionError, "absolute"):
                selector.write_private_partition(result, Path("relative.json"), checkout_root=checkout)
            destination = outer / "private" / "partition.json"
            selector.write_private_partition(result, destination, checkout_root=checkout)
            original = destination.read_bytes()
            with self.assertRaisesRegex(selector.PartitionError, "already_exists"):
                selector.write_private_partition(result, destination, checkout_root=checkout)
            self.assertEqual(destination.read_bytes(), original)

    def test_cli_reads_only_metadata_inventory_and_prints_no_private_ids_or_paths(self) -> None:
        with TemporaryDirectory(prefix="holdout-cli-") as tmp:
            root = Path(tmp).resolve()
            source_path = root / "metadata.json"
            output_path = root / "partition.json"
            source_path.write_text(json.dumps(inventory(stream("root-SECRET"))), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = selector.main(["--inventory", str(source_path), "--output", str(output_path)])
            self.assertEqual(status, 0)
            public = stdout.getvalue()
            self.assertNotIn("root-SECRET", public)
            self.assertNotIn(str(root), public)
            self.assertEqual(json.loads(public)["timing_label"], selector.TIMING_LABEL)
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
