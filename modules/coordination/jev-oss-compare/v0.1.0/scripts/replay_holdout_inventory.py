"""Build private, content-free metadata for exploratory session partitioning.

Raw source prose exists only inside the existing normalizer's in-memory
events. This builder reads event identity/provenance/count fields and emits
exactly replay_holdout's metadata schema. It never opens model receipts or
contacts a model. Stream IDs are unchanged from replay_sources so callers
can match them to baseline receipts privately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Sequence

from replay_holdout import (
    PartitionError,
    _checkout_root,
    _outside_checkout,
    _validate_inventory,
    write_private_partition,
)
from replay_sources import ReplayEvent, SourceIntegrityError, SourceReport, load_claude_jsonl


def build_inventory(events: Sequence[ReplayEvent], report: SourceReport) -> Dict[str, Any]:
    """Project normalized source metadata without accessing event text."""
    if report.malformed_rows:
        raise PartitionError("malformed_source_rows_prevent_complete_inventory")
    grouped: Dict[str, List[ReplayEvent]] = defaultdict(list)
    for event in events:
        grouped[event.stream_id].append(event)
    streams = []
    for stream_id in sorted(grouped):
        members = grouped[stream_id]
        sidechain_flags = {event.is_sidechain for event in members}
        if len(sidechain_flags) != 1:
            raise PartitionError("mixed_source_authority_within_stream")
        sidechain = next(iter(sidechain_flags))
        parent = None
        status = "root"
        if sidechain:
            prompts = [event for event in members if event.kind == "delegated_prompt"]
            first = min(prompts, key=lambda event: event.sequence) if prompts else None
            status = first.metadata.get("delegation_link_status", "unresolved") if first else "unresolved"
            if status not in {"resolved", "unresolved", "ambiguous"}:
                status = "unresolved"
            if status == "resolved":
                linked_parent = first.metadata.get("delegated_from_stream_id")
                if isinstance(linked_parent, str) and linked_parent:
                    parent = linked_parent
                else:
                    # An asserted resolution without a concrete parent cannot
                    # establish ancestry; keep the stream outside clean groups.
                    status = "unresolved"
        kinds = Counter(event.kind for event in members)
        streams.append({
            "stream_id": stream_id,
            "is_sidechain": sidechain,
            "parent_stream_id": parent,
            "delegation_link_status": status,
            "event_count": len(members),
            "events_by_kind": dict(sorted(kinds.items())),
        })
    inventory = {"schema_version": 1,
                 "source_hashes": dict(sorted(report.source_hashes.items())),
                 "streams": streams}
    _validate_inventory(inventory)
    return inventory


def _manifest_hash(source_hashes: Dict[str, str]) -> str:
    encoded = json.dumps(source_hashes, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private raw-source metadata inventory; no inference.")
    parser.add_argument("--source", required=True, type=Path,
                        help="Raw Claude Code source directory used by the baseline replay.")
    parser.add_argument("--output", required=True, type=Path,
                        help="Absolute new private metadata JSON outside the checkout.")
    args = parser.parse_args(argv)
    try:
        checkout = _checkout_root()
        destination = _outside_checkout(args.output, checkout)
        # Do not spend time normalizing a corpus when an immutable inventory
        # already occupies the requested destination.
        if destination.exists():
            raise PartitionError("partition_output_already_exists")
        events, report = load_claude_jsonl(args.source)
        inventory = build_inventory(events, report)
        write_private_partition(inventory, destination, checkout_root=checkout)
    except (PartitionError, SourceIntegrityError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc).split(":", 1)[0]}))
        return 2
    except (OSError, UnicodeError, ValueError):
        print(json.dumps({"status": "rejected", "reason": "source_inventory_io_failed"}))
        return 2
    statuses = Counter(stream["delegation_link_status"] for stream in inventory["streams"])
    print(json.dumps({
        "status": "written",
        "source_manifest_hash": _manifest_hash(inventory["source_hashes"]),
        "source_file_count": len(inventory["source_hashes"]),
        "stream_count": len(inventory["streams"]),
        "event_count": sum(stream["event_count"] for stream in inventory["streams"]),
        "stream_link_counts": dict(sorted(statuses.items())),
        "content_included": False,
        "inference_called": False,
        "receipt_outputs_read": False,
        "stream_ids_match_normalizer": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
