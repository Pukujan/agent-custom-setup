"""Transcript adapters: normalize any ACS-hotloaded agent into canonical rows.

Claude Code JSONL is adapter #1. Kilo Code (VS Code) is adapter #2 (task JSON).
Codex / Grok / others plug in here without changing SQLite/OTLP/Pass2.
"""

from __future__ import annotations

from .base import AdapterResult, TranscriptAdapter, get_adapter, list_adapters
from .claude_jsonl import ClaudeJsonlAdapter
from .kilo_tasks import KiloTasksAdapter, discover_kilo_roots, format_discovery_report

__all__ = [
    "AdapterResult",
    "TranscriptAdapter",
    "ClaudeJsonlAdapter",
    "KiloTasksAdapter",
    "discover_kilo_roots",
    "format_discovery_report",
    "get_adapter",
    "list_adapters",
]
