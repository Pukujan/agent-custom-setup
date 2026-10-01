"""Pass2 classify + embed: metamorphic stability and cosine≈1 for same text."""

from __future__ import annotations

from pathlib import Path

from session_ops_capture.classify import mock_classify_tool
from session_ops_capture.db import SessionOpsDB
from session_ops_capture.embed import HashingEmbedBackend, cosine, unpack_vector
from session_ops_capture.ingest import ingest_once
from session_ops_capture.pass2 import run_pass2

FIXTURES = Path(__file__).parent / "fixtures"


def test_reclassify_same_rows_same_labels(tmp_path: Path) -> None:
    db_path = tmp_path / "p2.sqlite"
    ingest_once(
        jsonl=FIXTURES / "sample_session.jsonl",
        db_path=db_path,
        export_otlp=False,
        force_mock_classify=True,
        force_hash_embed=True,
    )
    with SessionOpsDB(db_path) as db:
        a = [(r["uuid"], r["risk_class"], r["labels_json"]) for r in db.fetch_classifications()]
        run_pass2(db, force_mock_classify=True, force_hash_embed=True)
        b = [(r["uuid"], r["risk_class"], r["labels_json"]) for r in db.fetch_classifications()]
    assert a == b
    assert len(a) > 0


def test_embed_same_text_cosine_one() -> None:
    be = HashingEmbedBackend()
    t = "Bash | echo hello | ok-1"
    v1 = be.embed(t)
    v2 = be.embed(t)
    assert cosine(v1, v2) == 1.0


def test_embed_persisted_roundtrip_cosine(tmp_path: Path) -> None:
    db_path = tmp_path / "emb.sqlite"
    ingest_once(
        jsonl=FIXTURES / "sample_session.jsonl",
        db_path=db_path,
        export_otlp=False,
    )
    with SessionOpsDB(db_path) as db:
        rows = db.fetch_embeddings()
        assert len(rows) > 0
        be = HashingEmbedBackend()
        for r in rows:
            stored = unpack_vector(r["vector"])
            again = be.embed(r["text_redacted"] or "")
            assert cosine(stored, again) > 0.999


def test_mock_bash_is_gate_relevant_high() -> None:
    c = mock_classify_tool("Bash", '{"command":"rm -rf /tmp/x"}')
    assert c.gate_relevant is True
    assert c.risk_class == "high"


def test_pass2_counts_scale_with_tools(tmp_path: Path) -> None:
    r = ingest_once(
        jsonl=FIXTURES / "synthetic_30_tools.jsonl",
        db_path=tmp_path / "s30.sqlite",
        export_otlp=False,
    )
    assert r["counts"]["tool_calls"] == 30
    assert r["counts"]["classifications"] >= 30
    assert r["counts"]["embeddings"] >= 30
    assert r["pass2"]["embed_backend"] == "hashing-v1"
