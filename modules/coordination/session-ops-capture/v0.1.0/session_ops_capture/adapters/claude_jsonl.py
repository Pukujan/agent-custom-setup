"""Adapter #1: Claude Code session JSONL under ~/.claude/projects/."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..parse import extract_claude_records
from .base import AdapterResult, TranscriptAdapter, register_adapter


@register_adapter
class ClaudeJsonlAdapter(TranscriptAdapter):
    name = "claude-jsonl"

    def ingest_path(self, path: Path, **kwargs: Any) -> AdapterResult:
        parsed = extract_claude_records(path)
        sessions = []
        for s in parsed["sessions"]:
            meta = dict(s.get("meta") or {})
            meta["adapter"] = self.name
            meta["harness"] = "claude-code"
            sessions.append({**s, "meta": meta, "source": self.name})
        return AdapterResult(
            source=self.name,
            sessions=sessions,
            messages=parsed["messages"],
            tool_calls=parsed["tool_calls"],
        )
