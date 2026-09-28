"""Kilo Code adapter: discovery + synthetic task history normalize."""

from __future__ import annotations

from pathlib import Path

import pytest

from session_ops_capture.adapters import get_adapter, list_adapters
from session_ops_capture.adapters.kilo_tasks import (
    discover_kilo_roots,
    format_discovery_report,
)
from session_ops_capture.ingest import ingest_once
from session_ops_capture.redact import contains_forbidden_secret_pattern

FIXTURES = Path(__file__).parent / "fixtures" / "kilo_task_sample"


def test_kilo_in_adapter_registry() -> None:
    assert "kilo-tasks" in list_adapters()


def test_kilo_discovery_report_nonempty() -> None:
    roots = discover_kilo_roots()
    assert isinstance(roots, list)
    report = format_discovery_report(roots)
    assert "Kilo Code discovery" in report
    assert "api_conversation_history.json" in report


def test_kilo_adapter_ingests_sample(tmp_path: Path) -> None:
    r = ingest_once(
        jsonl=FIXTURES / "api_conversation_history.json",
        db_path=tmp_path / "kilo.sqlite",
        export_otlp=False,
        adapter_name="kilo-tasks",
    )
    assert r["adapter"] == "kilo-tasks"
    assert r["counts"]["tool_calls"] == 2
    assert r["counts"]["sessions"] == 1
    assert r["counts"]["classifications"] >= 2


def test_kilo_missing_path_fails_clearly() -> None:
    ad = get_adapter("kilo-tasks")
    with pytest.raises(FileNotFoundError) as ei:
        ad.ingest_path(Path("/nonexistent/kilo/task"))
    assert "Kilo Code discovery" in str(ei.value)


def test_kilo_redacts_secrets(tmp_path: Path) -> None:
    from session_ops_capture.db import SessionOpsDB

    ingest_once(
        jsonl=FIXTURES / "api_conversation_history.json",
        db_path=tmp_path / "k.sqlite",
        export_otlp=False,
        adapter_name="kilo-tasks",
    )
    with SessionOpsDB(tmp_path / "k.sqlite") as db:
        for blob in db.all_text_blobs():
            assert not contains_forbidden_secret_pattern(blob)
            assert "sk-test" not in blob
