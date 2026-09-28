#!/usr/bin/env python3
from __future__ import annotations
import re
SECRETISH = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|bearer)\s*[=:]\s*\S+")
LONG_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")
SK_PREFIX = re.compile(r"\b(sk|pk|ghp|gho|xox[baprs])-[A-Za-z0-9_-]{8,}\b")
def redact(text: str) -> str:
    if not text:
        return text
    out = SECRETISH.sub(r"\1=[REDACTED]", text)
    out = SK_PREFIX.sub("[REDACTED]", out)
    out = LONG_HEX.sub("[REDACTED]", out)
    return out
