#!/usr/bin/env python3
"""OpenRouter decisions client for typesafe/jev-1.13 (ACS gates).

Mock path is default (CI). Live path only when ACS_JEV_LIVE=1 and OPENROUTER_API_KEY set.
Never prints secrets. Embeddings are NOT called here (not on JEV hot path).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MODEL = "typesafe/jev-1.13"
DEFAULT_BASE = "https://openrouter.ai/api/alpha"
DEFAULT_PATH = "/decisions"

def env_live_enabled() -> bool:
    return os.environ.get("ACS_JEV_LIVE", "").strip().lower() in ("1", "true", "yes")

def resolve_api_key() -> Optional[str]:
    # Never log this value.
    for k in ("OPENROUTER_API_KEY", "ACS_OPENROUTER_API_KEY"):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    return None

def decide_openrouter(
    *,
    state: str,
    question_name: str,
    instructions: str,
    criteria: Dict[str, str],
    model: str = DEFAULT_MODEL,
    timeout_s: float = 20.0,
) -> Tuple[str, float, str]:
    """Return (choice, confidence, model_id). Raises on transport/parse errors."""
    api_key = resolve_api_key()
    if not api_key:
        raise RuntimeError("openrouter_key_missing")
    base = os.environ.get("ACS_JEV_BASE_URL", DEFAULT_BASE).rstrip("/")
    path = os.environ.get("ACS_JEV_PATH", DEFAULT_PATH)
    body = {
        "model": model,
        "state": state,
        "questions": {
            question_name: {
                "type": "choice",
                "instructions": instructions,
                "criteria": criteria,
            }
        },
    }
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Pukujan/agent-custom-setup",
            "X-Title": "acs-jev-gates",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    answers = (raw.get("answers") or {}) if isinstance(raw, dict) else {}
    ans = answers.get(question_name) or {}
    choice = str(ans.get("choice") or "insufficient")
    conf = float(ans.get("confidence") or 0.0)
    mid = str(raw.get("model") or model) if isinstance(raw, dict) else model
    return choice, conf, mid
