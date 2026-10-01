"""Optional jev-gate-pin / ACS gate JSONL adapter (harness-agnostic)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..parse import extract_gate_events
from .base import AdapterResult, TranscriptAdapter, register_adapter


@register_adapter
class GateJsonlAdapter(TranscriptAdapter):
    name = "gate-jsonl"

    def ingest_path(self, path: Path, **kwargs: Any) -> AdapterResult:
        default_session_id: Optional[str] = kwargs.get("default_session_id")
        events = extract_gate_events(path, default_session_id=default_session_id)
        return AdapterResult(source=self.name, gate_events=events)
