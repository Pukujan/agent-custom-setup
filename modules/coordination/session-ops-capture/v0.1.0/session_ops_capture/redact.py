"""Redact secret-looking values (mirrors jev-gate-pin log_event style + sk-/ghp-)."""

from __future__ import annotations

import json
import re
from typing import Any

SECRETISH = re.compile(
    r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[=:]\s*\S+"
)
LONG_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")
SK_PREFIX = re.compile(r"\b(sk|pk|ghp|gho|xox[baprs])-[A-Za-z0-9_-]{8,}\b")
SK_TESTISH = re.compile(r"\b(sk-test|sk-live|ghp_|gho_)[A-Za-z0-9_-]*\b", re.I)
BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-+=/]{8,}")


def redact(text: str) -> str:
    if not text:
        return text
    # Bearer / token prefixes first so Authorization: Bearer <tok> is fully scrubbed
    out = BEARER.sub("bearer [REDACTED]", text)
    out = SK_PREFIX.sub("[REDACTED]", out)
    out = SK_TESTISH.sub("[REDACTED]", out)
    out = SECRETISH.sub(r"\1=[REDACTED]", out)
    out = LONG_HEX.sub("[REDACTED]", out)
    return out


def redact_obj(value: Any) -> Any:
    """Deep-redact strings inside nested JSON-compatible structures."""
    if value is None:
        return None
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(k): redact_obj(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_obj(v) for v in value]
    if isinstance(value, (int, float, bool)):
        return value
    return redact(str(value))


def dumps_redacted(value: Any) -> str:
    return json.dumps(redact_obj(value), ensure_ascii=False, sort_keys=True)


def contains_forbidden_secret_pattern(text: str) -> bool:
    """True if raw secret patterns remain (for metamorphic / property tests)."""
    if not text:
        return False
    if SK_PREFIX.search(text) or SK_TESTISH.search(text):
        return True
    if re.search(r"(?i)api_key\s*=\s*(?!\[REDACTED\])\S+", text):
        return True
    if re.search(r"(?i)\bbearer\s+(?!\[REDACTED\])[A-Za-z0-9._\-+=/]{8,}", text):
        return True
    return False
