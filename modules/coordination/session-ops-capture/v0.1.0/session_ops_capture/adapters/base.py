"""Adapter interface for ACS-wide session sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type


@dataclass
class AdapterResult:
    """Canonical rows shared by all harness adapters."""

    source: str  # e.g. claude-code | codex | grok | generic-jsonl
    sessions: List[Dict[str, Any]] = field(default_factory=list)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    gate_events: List[Dict[str, Any]] = field(default_factory=list)


class TranscriptAdapter(ABC):
    """Parse a harness-specific transcript into AdapterResult."""

    name: str = "base"

    @abstractmethod
    def ingest_path(self, path: Path, **kwargs: Any) -> AdapterResult:
        raise NotImplementedError


_REGISTRY: Dict[str, Type[TranscriptAdapter]] = {}


def register_adapter(cls: Type[TranscriptAdapter]) -> Type[TranscriptAdapter]:
    _REGISTRY[cls.name] = cls
    return cls


def get_adapter(name: str) -> TranscriptAdapter:
    if name not in _REGISTRY:
        # Lazy import builtins
        from . import claude_jsonl  # noqa: F401
        from . import gate_jsonl  # noqa: F401
        from . import kilo_tasks  # noqa: F401
    if name not in _REGISTRY:
        raise KeyError(f"unknown adapter {name!r}; known={sorted(_REGISTRY)}")
    return _REGISTRY[name]()


def list_adapters() -> List[str]:
    from . import claude_jsonl  # noqa: F401
    from . import gate_jsonl  # noqa: F401
    from . import kilo_tasks  # noqa: F401

    return sorted(_REGISTRY)
