"""Adapter: Kilo Code (VS Code) task transcripts.

Kilo Code 7.8.x (kilocode.kilo-code) stores per-task files under VS Code
globalStorage, same shape as Cline/Roo forks:

  %APPDATA%\\Code\\User\\globalStorage\\kilocode.kilo-code\\tasks\\<taskId>\\
    api_conversation_history.json
    ui_messages.json

taskHistory lives in VS Code globalState (not a plain file). On machines with
no completed Kilo tasks yet, discover_* returns candidate roots and ingest
fails clearly until a task dir or history JSON is provided.
"""

from __future__ import annotations

import json
import os
import uuid as uuidlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..redact import dumps_redacted, redact
from .base import AdapterResult, TranscriptAdapter, register_adapter

API_FILE = "api_conversation_history.json"
UI_FILE = "ui_messages.json"


def _appdata() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")


def discover_kilo_roots() -> List[Dict[str, Any]]:
    """Probe common Windows/macOS/Linux locations for Kilo task storage."""
    home = Path.home()
    appdata = _appdata()
    candidates = [
        appdata / "Code" / "User" / "globalStorage" / "kilocode.kilo-code",
        appdata / "Code - Insiders" / "User" / "globalStorage" / "kilocode.kilo-code",
        appdata / "Cursor" / "User" / "globalStorage" / "kilocode.kilo-code",
        home / ".kilocode",
        home / ".kilo",
        home / ".vscode" / "extensions",
    ]
    out: List[Dict[str, Any]] = []
    for p in candidates:
        info: Dict[str, Any] = {"path": str(p), "exists": p.exists()}
        if p.exists():
            tasks = p / "tasks"
            info["tasks_dir"] = str(tasks)
            info["tasks_dir_exists"] = tasks.is_dir()
            if tasks.is_dir():
                kids = [c.name for c in tasks.iterdir() if c.is_dir()]
                info["task_count"] = len(kids)
                info["sample_tasks"] = kids[:5]
            else:
                info["task_count"] = 0
                info["note"] = (
                    "Extension storage present but no tasks/ yet — "
                    "run a Kilo session in VS Code, or pass --jsonl to a task "
                    f"folder / {API_FILE}."
                )
        out.append(info)
    return out


def format_discovery_report(roots: Optional[Sequence[Dict[str, Any]]] = None) -> str:
    roots = list(roots if roots is not None else discover_kilo_roots())
    lines = ["Kilo Code discovery:"]
    for r in roots:
        lines.append(f"  - {r.get('path')} exists={r.get('exists')}")
        if r.get("tasks_dir_exists"):
            lines.append(
                f"      tasks={r.get('task_count')} sample={r.get('sample_tasks')}"
            )
        elif r.get("note"):
            lines.append(f"      note: {r['note']}")
    lines.append(
        f"Expected task files: tasks/<id>/{API_FILE} and optional {UI_FILE}"
    )
    lines.append(
        "Confirmed on Teresa-Pujan: extension kilocode.kilo-code 7.8.1; "
        "globalStorage/kilocode.kilo-code present; tasks/ absent until first run."
    )
    return "\n".join(lines)


def _as_blocks(content: Any) -> List[Dict[str, Any]]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [c for c in content if isinstance(c, dict)]
    if isinstance(content, dict) and "type" in content:
        return [content]
    return [{"type": "text", "text": str(content)}]


def _load_history(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("messages", "history", "apiConversationHistory"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
    raise ValueError(
        f"Unrecognized Kilo history shape at {path}; expected JSON array of "
        f"messages or object with messages/history. Discovery:\n"
        f"{format_discovery_report()}"
    )


@register_adapter
class KiloTasksAdapter(TranscriptAdapter):
    """Normalize Kilo task dir or api_conversation_history.json → canonical rows."""

    name = "kilo-tasks"

    def ingest_path(self, path: Path, **kwargs: Any) -> AdapterResult:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"Kilo path not found: {path}\n{format_discovery_report()}"
            )

        history_path: Optional[Path] = None
        task_id = kwargs.get("task_id")
        cwd = kwargs.get("cwd")

        if path.is_dir():
            if (path / API_FILE).is_file():
                history_path = path / API_FILE
                task_id = task_id or path.name
            elif (path / "tasks").is_dir():
                raise FileNotFoundError(
                    f"Pass a specific task directory under {path / 'tasks'}, "
                    f"not the storage root.\n{format_discovery_report()}"
                )
            else:
                raise FileNotFoundError(
                    f"No {API_FILE} in {path}.\n{format_discovery_report()}"
                )
        else:
            if path.name != API_FILE and path.suffix.lower() != ".json":
                raise ValueError(
                    f"Expected {API_FILE} or a Kilo task directory; got {path}\n"
                    f"{format_discovery_report()}"
                )
            history_path = path
            task_id = task_id or path.parent.name

        assert history_path is not None
        messages_raw = _load_history(history_path)
        sid = str(task_id or uuidlib.uuid4())
        sessions = [
            {
                "session_id": sid,
                "cwd": cwd,
                "started_at": None,
                "ended_at": None,
                "meta": {
                    "adapter": self.name,
                    "harness": "kilo-code",
                    "source_path": str(history_path),
                },
                "source": self.name,
            }
        ]
        messages: List[Dict[str, Any]] = []
        tool_calls: Dict[str, Dict[str, Any]] = {}
        interaction_index = 0
        started = None
        ended = None

        for i, msg in enumerate(messages_raw):
            role = msg.get("role") or msg.get("type")
            ts = msg.get("ts") or msg.get("timestamp") or msg.get("time")
            if ts:
                started = started or ts
                ended = ts
            mid = str(msg.get("id") or msg.get("uuid") or f"{sid}-msg-{i}")
            blocks = _as_blocks(msg.get("content"))
            if role in ("user", "human"):
                interaction_index += 1
                role_n = "user"
            elif role in ("assistant", "ai", "model"):
                role_n = "assistant"
            else:
                role_n = str(role) if role else "unknown"

            messages.append(
                {
                    "uuid": mid,
                    "session_id": sid,
                    "parent_uuid": None,
                    "role": role_n,
                    "type": role_n,
                    "timestamp": ts,
                    "content_redacted": dumps_redacted(
                        [
                            {
                                "type": b.get("type"),
                                "text": redact(str(b.get("text") or ""))[:2000]
                                if b.get("type") == "text"
                                else None,
                                "id": b.get("id"),
                                "name": b.get("name"),
                                "tool_use_id": b.get("tool_use_id"),
                            }
                            for b in blocks
                        ]
                    ),
                    "interaction_index": interaction_index or None,
                }
            )

            for b in blocks:
                if b.get("type") == "tool_use":
                    tid = str(b.get("id") or f"tool-{mid}")
                    tool_calls[tid] = {
                        "uuid": tid,
                        "session_id": sid,
                        "message_uuid": mid,
                        "tool_name": redact(str(b.get("name") or "")),
                        "tool_use_id": tid,
                        "input_redacted": dumps_redacted(b.get("input")),
                        "result_redacted": None,
                        "timestamp": ts,
                        "interaction_index": interaction_index or None,
                    }
                elif b.get("type") == "tool_result":
                    tid = str(b.get("tool_use_id") or "")
                    if not tid:
                        continue
                    existing = tool_calls.get(
                        tid,
                        {
                            "uuid": tid,
                            "session_id": sid,
                            "message_uuid": mid,
                            "tool_name": None,
                            "tool_use_id": tid,
                            "input_redacted": None,
                            "result_redacted": None,
                            "timestamp": ts,
                            "interaction_index": interaction_index or None,
                        },
                    )
                    content = b.get("content")
                    if isinstance(content, str) and len(content) > 4000:
                        content = content[:4000] + "…[truncated]"
                    existing["result_redacted"] = dumps_redacted(content)
                    tool_calls[tid] = existing

        sessions[0]["started_at"] = started
        sessions[0]["ended_at"] = ended
        return AdapterResult(
            source=self.name,
            sessions=sessions,
            messages=messages,
            tool_calls=list(tool_calls.values()),
        )
