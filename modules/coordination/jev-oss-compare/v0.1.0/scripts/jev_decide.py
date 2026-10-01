#!/usr/bin/env python3
"""Thin OpenRouter typesafe/jev decisions helper for compare lane.
Never prints secrets. Live only when ACS_JEV_LIVE=1 and key present.
"""
from __future__ import annotations
import json, os, time, urllib.request
from typing import Dict, Tuple

DEFAULT_MODEL = "typesafe/jev-1.13"
DEFAULT_BASE = "https://openrouter.ai/api/alpha"

def live_enabled() -> bool:
    return os.environ.get("ACS_JEV_LIVE", "").strip().lower() in ("1", "true", "yes")

def _key() -> str | None:
    for k in ("OPENROUTER_API_KEY", "ACS_OPENROUTER_API_KEY"):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    return None

def decide_choice(state: str, question: str, instructions: str, criteria: Dict[str, str],
                  *, timeout_s: float = 20.0) -> Tuple[str, float, str, float]:
    """Return (choice, confidence, model, latency_ms)."""
    if not live_enabled():
        raise RuntimeError("live_not_enabled")
    api_key = _key()
    if not api_key:
        raise RuntimeError("openrouter_key_missing")
    base = os.environ.get("ACS_JEV_BASE_URL", DEFAULT_BASE).rstrip("/")
    body = {
        "model": os.environ.get("ACS_JEV_MODEL", DEFAULT_MODEL),
        "state": state[:6000],
        "questions": {question: {"type": "choice", "instructions": instructions, "criteria": criteria}},
    }
    req = urllib.request.Request(
        f"{base}/decisions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Pukujan/agent-custom-setup",
            "X-Title": "acs-jev-oss-compare",
        },
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    ms = (time.perf_counter() - t0) * 1000
    ans = (raw.get("answers") or {}).get(question) or {}
    choice = str(ans.get("choice") or "escalate")
    conf = float(ans.get("confidence") or 0.0)
    mid = str(raw.get("model") or DEFAULT_MODEL)
    return choice, conf, mid, ms
