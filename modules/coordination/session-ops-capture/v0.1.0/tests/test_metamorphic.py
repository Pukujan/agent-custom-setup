"""Metamorphic tests: reorder/duplicate JSONL lines → same DB fingerprint; no secrets stored."""

from __future__ import annotations

import random
from pathlib import Path

from session_ops_capture.db import SessionOpsDB
from session_ops_capture.ingest import ingest_once
from session_ops_capture.redact import contains_forbidden_secret_pattern

FIXTURES = Path(__file__).parent / "fixtures"


def _shuffle_and_dup(src: Path, dest: Path, seed: int = 42) -> None:
    lines = [ln for ln in src.read_text(encoding="utf-8").splitlines() if ln.strip()]
    rng = random.Random(seed)
    # duplicate a few lines then shuffle
    extra = list(lines)
    if lines:
        extra.extend(rng.sample(lines, k=min(3, len(lines))))
    rng.shuffle(extra)
    dest.write_text("\n".join(extra) + "\n", encoding="utf-8")


def test_metamorphic_reorder_duplicate_same_fingerprint(tmp_path: Path) -> None:
    src = FIXTURES / "sample_session.jsonl"
    mutated = tmp_path / "mutated.jsonl"
    _shuffle_and_dup(src, mutated)

    db_a = tmp_path / "a.sqlite"
    db_b = tmp_path / "b.sqlite"
    ra = ingest_once(jsonl=src, db_path=db_a, export_otlp=False)
    rb = ingest_once(jsonl=mutated, db_path=db_b, export_otlp=False)
    assert ra["fingerprint"] == rb["fingerprint"]
    assert ra["counts"] == rb["counts"]


def test_metamorphic_redaction_never_stores_sk_or_ghp(tmp_path: Path) -> None:
    db_path = tmp_path / "ops.sqlite"
    ingest_once(
        jsonl=FIXTURES / "sample_session.jsonl",
        db_path=db_path,
        gate_jsonl=FIXTURES / "sample_gate.jsonl",
        export_otlp=False,
    )
    with SessionOpsDB(db_path) as db:
        blobs = list(db.all_text_blobs())
    joined = "\n".join(blobs)
    assert "sk-test" not in joined
    assert "ghp-" not in joined.lower() or "[REDACTED]" in joined
    for blob in blobs:
        assert not contains_forbidden_secret_pattern(blob), blob[:200]


def test_synthetic_thirty_tools_count(tmp_path: Path) -> None:
    r = ingest_once(
        jsonl=FIXTURES / "synthetic_30_tools.jsonl",
        db_path=tmp_path / "s30.sqlite",
        export_otlp=False,
    )
    assert r["counts"]["tool_calls"] == 30
    assert r["counts"]["sessions"] == 1
