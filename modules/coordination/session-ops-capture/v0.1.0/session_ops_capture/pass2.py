"""Pass2: classify + embed over canonical rows (batch or after live ingest)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .classify import classify_message, classify_tool
from .db import SessionOpsDB
from .embed import EmbedBackend, get_embed_backend, pack_vector
from .redact import redact


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tool_embed_text(tc: Dict[str, Any]) -> str:
    parts = [
        str(tc.get("tool_name") or ""),
        str(tc.get("input_redacted") or "")[:1500],
        str(tc.get("result_redacted") or "")[:800],
    ]
    return redact(" | ".join(p for p in parts if p))


def _message_embed_text(msg: Dict[str, Any]) -> str:
    return redact(
        f"{msg.get('role') or ''} {str(msg.get('content_redacted') or '')[:2000]}"
    )


def run_pass2(
    db: SessionOpsDB,
    *,
    force_mock_classify: bool = True,
    force_hash_embed: bool = True,
    embed_messages: bool = True,
    backend: Optional[EmbedBackend] = None,
) -> Dict[str, Any]:
    """
    Label tool_calls (+ messages) and write embeddings.

    Defaults force mock/hash so pytest and CI never hit paid APIs or model downloads.
    Live evidence may set force_*=False and configure ACS_JEV_CLASSIFIER_URL /
    ACS_EMBED_BACKEND.
    """
    be = backend or get_embed_backend(force_hash=force_hash_embed)
    n_cls = 0
    n_emb = 0
    ts = _now()

    for row in db.fetch_tool_calls():
        tc = {k: row[k] for k in row.keys()}
        cls = classify_tool(
            tc.get("tool_name") or "",
            tc.get("input_redacted"),
            force_mock=force_mock_classify,
        )
        fields = cls.as_row_fields()
        db.upsert_classification(
            {
                "uuid": f"tool:{tc['uuid']}",
                "entity_type": "tool_call",
                "session_id": tc.get("session_id"),
                "classified_at": ts,
                **fields,
            }
        )
        n_cls += 1
        text = _tool_embed_text(tc)
        vec = be.embed(text)
        db.upsert_embedding(
            {
                "uuid": f"tool:{tc['uuid']}",
                "entity_type": "tool_call",
                "session_id": tc.get("session_id"),
                "backend": be.name,
                "dim": be.dim,
                "text_redacted": text[:4000],
                "vector": pack_vector(vec),
                "embedded_at": ts,
            }
        )
        n_emb += 1

    if embed_messages:
        for row in db.fetch_messages():
            msg = {k: row[k] for k in row.keys()}
            # Classify user/assistant messages lightly
            if msg.get("role") in ("user", "assistant") or msg.get("type") in (
                "user",
                "assistant",
            ):
                cls = classify_message(
                    msg.get("role"),
                    msg.get("content_redacted"),
                    force_mock=force_mock_classify,
                )
                fields = cls.as_row_fields()
                db.upsert_classification(
                    {
                        "uuid": f"msg:{msg['uuid']}",
                        "entity_type": "message",
                        "session_id": msg.get("session_id"),
                        "classified_at": ts,
                        **fields,
                    }
                )
                n_cls += 1
            text = _message_embed_text(msg)
            vec = be.embed(text)
            db.upsert_embedding(
                {
                    "uuid": f"msg:{msg['uuid']}",
                    "entity_type": "message",
                    "session_id": msg.get("session_id"),
                    "backend": be.name,
                    "dim": be.dim,
                    "text_redacted": text[:4000],
                    "vector": pack_vector(vec),
                    "embedded_at": ts,
                }
            )
            n_emb += 1

    db.commit()
    return {
        "classifications": n_cls,
        "embeddings": n_emb,
        "embed_backend": be.name,
        "embed_dim": be.dim,
        "classify_mode": "mock" if force_mock_classify else "auto",
    }
