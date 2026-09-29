"""Adapter registry: Claude is #1; interface lists reserved harnesses."""

from __future__ import annotations

from pathlib import Path

from session_ops_capture.adapters import get_adapter, list_adapters
from session_ops_capture.ingest import ingest_once

FIXTURES = Path(__file__).parent / "fixtures"


def test_list_adapters_includes_claude_and_gate() -> None:
    names = list_adapters()
    assert "claude-jsonl" in names
    assert "gate-jsonl" in names


def test_claude_adapter_ingest(tmp_path: Path) -> None:
    r = ingest_once(
        jsonl=FIXTURES / "sample_session.jsonl",
        db_path=tmp_path / "a.sqlite",
        export_otlp=False,
        adapter_name="claude-jsonl",
        run_pass2_flag=False,
    )
    assert r["adapter"] == "claude-jsonl"
    assert r["counts"]["tool_calls"] >= 3


def test_get_adapter_claude() -> None:
    ad = get_adapter("claude-jsonl")
    assert ad.name == "claude-jsonl"
