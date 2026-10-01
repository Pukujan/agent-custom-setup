"""Content-free exploratory whole-session partitioning; never calls a model.

This selector was added after inference began. Its output is explicitly a
post-inference / pre-analysis exploratory partition, not a preregistered
holdout or evidence that a holdout benchmark passed.

The private input is metadata only::

    {"schema_version": 1,
     "source_hashes": {"opaque_locator_hash": "64-character SHA256"},
     "streams": [{"stream_id": "private source stream ID",
                  "is_sidechain": false, "parent_stream_id": null,
                  "delegation_link_status": "root", "event_count": 2,
                  "events_by_kind": {"human_user": 2}}]}

For children, is_sidechain is true and delegation_link_status is resolved,
unresolved, or ambiguous. Only a proven, acyclic path to an existing root
joins that root's group. Unresolved ancestry is a separate quarantine group.
No transcript text, expected decisions, model outputs, or source paths are
accepted. Ranking uses only the seed and root identifier, never content,
file hashes, event counts, source order, or model outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


DEFAULT_SEED = "ACS-0004-exploratory-session-partition-v1"
TIMING_LABEL = "post-inference / pre-analysis exploratory partition"
_STREAM_FIELDS = {
    "stream_id", "is_sidechain", "parent_stream_id",
    "delegation_link_status", "event_count", "events_by_kind",
}
_EVENT_KINDS = {
    "human_user", "meta_user", "delegated_prompt", "assistant_text",
    "tool_call", "tool_result", "compact_boundary",
}


class PartitionError(ValueError):
    """A metadata inventory or output destination is unsafe or incomplete."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _is_hash(value: Any, lengths: Sequence[int] = (64,)) -> bool:
    return (isinstance(value, str) and len(value) in lengths
            and all(char in "0123456789abcdef" for char in value))


def _opaque_id(stream_id: str, seed: str) -> str:
    return hmac.new(seed.encode("utf-8"),
                    ("opaque-stream-v1\0" + stream_id).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _rank(root_id: str, seed: str) -> str:
    return hmac.new(seed.encode("utf-8"),
                    ("root-ranking-v1\0" + root_id).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _validate_inventory(inventory: Any) -> Dict[str, Mapping[str, Any]]:
    if (not isinstance(inventory, dict)
            or set(inventory) != {"schema_version", "source_hashes", "streams"}
            or inventory.get("schema_version") != 1):
        raise PartitionError("metadata_inventory_schema_invalid")
    source_hashes = inventory["source_hashes"]
    if (not isinstance(source_hashes, dict) or not source_hashes
            or any(not _is_hash(key, (16, 64)) or not _is_hash(value)
                   for key, value in source_hashes.items())):
        raise PartitionError("source_manifest_requires_hashed_locators_and_sha256")
    streams = inventory["streams"]
    if not isinstance(streams, list) or not streams:
        raise PartitionError("stream_inventory_must_be_nonempty")
    by_id: Dict[str, Mapping[str, Any]] = {}
    for stream in streams:
        if not isinstance(stream, dict) or set(stream) != _STREAM_FIELDS:
            raise PartitionError("stream_metadata_fields_invalid")
        stream_id = stream["stream_id"]
        if not isinstance(stream_id, str) or not stream_id or stream_id in by_id:
            raise PartitionError("stream_ids_must_be_nonempty_and_unique")
        if type(stream["is_sidechain"]) is not bool:
            raise PartitionError("is_sidechain_must_be_boolean")
        parent = stream["parent_stream_id"]
        if parent is not None and (not isinstance(parent, str) or not parent):
            raise PartitionError("parent_stream_id_invalid")
        status = stream["delegation_link_status"]
        if not isinstance(status, str) or status not in {"root", "resolved", "unresolved", "ambiguous"}:
            raise PartitionError("delegation_link_status_invalid")
        if not stream["is_sidechain"] and (parent is not None or status != "root"):
            raise PartitionError("root_stream_cannot_have_delegation_parent")
        if stream["is_sidechain"] and status == "root":
            raise PartitionError("sidechain_cannot_claim_root_status")
        count = stream["event_count"]
        kinds = stream["events_by_kind"]
        if (type(count) is not int or count < 0 or not isinstance(kinds, dict)
                or any(kind not in _EVENT_KINDS or type(value) is not int or value < 0
                       for kind, value in kinds.items())
                or sum(kinds.values()) != count):
            raise PartitionError("event_counts_must_match_known_metadata_kinds")
        by_id[stream_id] = stream
    return by_id


def _root_for(stream_id: str, by_id: Mapping[str, Mapping[str, Any]]) -> tuple[str | None, str | None]:
    visited = set()
    current = stream_id
    while True:
        if current in visited:
            return None, "ancestry_cycle"
        visited.add(current)
        stream = by_id.get(current)
        if stream is None:
            return None, "parent_stream_missing"
        if not stream["is_sidechain"]:
            return current, None
        status = stream["delegation_link_status"]
        if status != "resolved":
            reason = "ambiguous_ancestry" if status == "ambiguous" else "unresolved_ancestry"
            return None, reason
        parent = stream["parent_stream_id"]
        if parent is None:
            return None, "resolved_link_missing_parent"
        current = parent


def _counts(streams: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    kinds: Counter[str] = Counter()
    for stream in streams:
        kinds.update(stream["events_by_kind"])
    return {"streams": len(streams),
            "events": sum(stream["event_count"] for stream in streams),
            "events_by_kind": dict(sorted(kinds.items()))}


def build_partition(inventory: Any, *, seed: str = DEFAULT_SEED,
                    holdout_fraction: str = "0.25") -> Dict[str, Any]:
    """Partition metadata; the input is never mutated or selected by outcomes."""
    by_id = _validate_inventory(inventory)
    if not isinstance(seed, str) or not seed:
        raise PartitionError("selection_seed_required")
    try:
        fraction = Decimal(str(holdout_fraction))
    except InvalidOperation as exc:
        raise PartitionError("holdout_fraction_invalid") from exc
    if not fraction.is_finite() or not 0 < fraction < 1:
        raise PartitionError("holdout_fraction_must_be_between_zero_and_one")

    groups: Dict[str, List[Mapping[str, Any]]] = {}
    quarantined: List[Dict[str, Any]] = []
    quarantine_sources: List[Mapping[str, Any]] = []
    for stream_id, stream in by_id.items():
        root_id, reason = _root_for(stream_id, by_id)
        if root_id is None:
            quarantine_sources.append(stream)
            quarantined.append({"stream_id_hash": _opaque_id(stream_id, seed),
                                "ancestry_status": reason, **_counts([stream])})
        else:
            groups.setdefault(root_id, []).append(stream)

    ranked_roots = sorted(groups, key=lambda root_id: (_rank(root_id, seed), root_id))
    reserve_count = int((len(ranked_roots) * fraction).to_integral_value(rounding=ROUND_CEILING))
    reserved = set(ranked_roots[:reserve_count])
    root_groups = []
    partition_sources: Dict[str, List[Mapping[str, Any]]] = {
        "exploratory_reserved": [], "exploratory_comparison": [],
    }
    for root_id, members in groups.items():
        partition = "exploratory_reserved" if root_id in reserved else "exploratory_comparison"
        partition_sources[partition].extend(members)
        root_groups.append({
            "root_stream_id_hash": _opaque_id(root_id, seed),
            "partition": partition,
            "stream_id_hashes": sorted(_opaque_id(member["stream_id"], seed) for member in members),
            **_counts(members),
        })
    root_groups.sort(key=lambda group: group["root_stream_id_hash"])
    quarantined.sort(key=lambda stream: stream["stream_id_hash"])

    output: Dict[str, Any] = {
        "schema_version": 1,
        "timing_label": TIMING_LABEL,
        "preregistered_holdout": False,
        "holdout_benchmark_passed": False,
        "content_included": False,
        "source_manifest_hash": _sha256(inventory["source_hashes"]),
        "selection_seed_hash": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        "requested_reserved_fraction": str(fraction.normalize()),
        "source_file_count": len(inventory["source_hashes"]),
        "root_count": len(groups),
        "reserved_root_count": reserve_count,
        "comparison_root_count": len(groups) - reserve_count,
        "total_counts": _counts(list(by_id.values())),
        "partition_counts": {key: _counts(value) for key, value in partition_sources.items()},
        "unresolved_ancestry_counts": _counts(quarantine_sources),
        "root_groups": root_groups,
        "unresolved_ancestry": quarantined,
        "limitations": [
            "Inference began before this selector; this is a post-inference / pre-analysis exploratory partition.",
            "No transcript or model decision output is read by this selector; review history cannot be independently verified here.",
            "Resolved descendants stay with their root; unresolved, ambiguous, missing, or cyclic ancestry is excluded from clean partition coverage.",
            "Root groups contain only source-proven descendants; omitted ancestry prevents a claim of complete whole-conversation coverage.",
            "Opaque IDs preserve grouping, not independent statistical samples; small cohorts may reserve every root.",
            "This partition does not demonstrate model correctness, accuracy, or a passed holdout benchmark.",
        ],
    }
    output["selection_hash"] = _sha256(output)
    return output


def _checkout_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    raise PartitionError("checkout_root_not_found")


def _outside_checkout(path: Path, checkout_root: Path) -> Path:
    if not path.is_absolute():
        raise PartitionError("private_path_must_be_absolute")
    resolved = path.expanduser().resolve()
    if resolved.is_relative_to(checkout_root.resolve()):
        raise PartitionError("private_path_must_be_outside_checkout")
    return resolved


def write_private_partition(output: Mapping[str, Any], destination: Path, *,
                            checkout_root: Path | None = None) -> None:
    """Write once, outside the checkout; do not replace an existing freeze."""
    resolved = _outside_checkout(destination, checkout_root or _checkout_root())
    resolved.parent.mkdir(parents=True, exist_ok=True)
    try:
        with resolved.open("x", encoding="utf-8") as handle:
            json.dump(output, handle, sort_keys=True, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        raise PartitionError("partition_output_already_exists") from exc


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private metadata-only exploratory session partition.")
    parser.add_argument("--inventory", required=True, type=Path,
                        help="Absolute private metadata-only inventory, outside the checkout.")
    parser.add_argument("--output", required=True, type=Path,
                        help="Absolute new private partition file, outside the checkout.")
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--holdout-fraction", default="0.25")
    args = parser.parse_args(argv)
    try:
        checkout = _checkout_root()
        inventory_path = _outside_checkout(args.inventory, checkout)
        # Validate output before reading even the content-free inventory.
        _outside_checkout(args.output, checkout)
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        output = build_partition(inventory, seed=args.seed, holdout_fraction=args.holdout_fraction)
        write_private_partition(output, args.output, checkout_root=checkout)
    except PartitionError as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}))
        return 2
    except (OSError, UnicodeError, json.JSONDecodeError):
        print(json.dumps({"status": "rejected", "reason": "private_inventory_or_output_io_failed"}))
        return 2
    print(json.dumps({"status": "written", "timing_label": output["timing_label"],
                      "source_manifest_hash": output["source_manifest_hash"],
                      "selection_hash": output["selection_hash"],
                      "root_count": output["root_count"],
                      "reserved_root_count": output["reserved_root_count"],
                      "unresolved_ancestry_counts": output["unresolved_ancestry_counts"],
                      "content_included": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
