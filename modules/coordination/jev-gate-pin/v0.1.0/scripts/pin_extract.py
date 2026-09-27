#!/usr/bin/env python3
"""Constraint pin extract / reinject stub for jev-gate-pin.

Heuristic: keep short lines mentioning MUST / hosted / API / key path / model id.
No secrets — callers must pass already-redacted text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Iterable, List

DEFAULT_PIN_CAP = 1200  # chars for reinjected pin block (~47-token class pins OK)

PIN_PATTERNS = [
    re.compile(r"\bMUST\b", re.I),
    re.compile(r"\bMUST\s+NOT\b", re.I),
    re.compile(r"\bhosted\b", re.I),
    re.compile(r"\bself[- ]?host\b", re.I),
    re.compile(r"\bAPI\b"),
    re.compile(r"\bkey\s*path\b", re.I),
    re.compile(r"\bmodel\s*id\b", re.I),
    re.compile(r"\bfish\.audio\b", re.I),
    re.compile(r"\bpip\s+install\b", re.I),
]


def _lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]


def is_pin_line(line: str) -> bool:
    return any(p.search(line) for p in PIN_PATTERNS)


def extract_pins(brief: str, corrections: Iterable[str] | None = None) -> List[str]:
    """Extract short constraint pins from brief + corrections."""
    pins: List[str] = []
    seen = set()
    for src in [brief or ""] + list(corrections or []):
        for line in _lines(src if isinstance(src, str) else str(src)):
            if not is_pin_line(line):
                continue
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            pins.append(line)
    return pins


def reinject(pins: Iterable[str], cap: int = DEFAULT_PIN_CAP) -> str:
    """Return a capped reinjection string from pins."""
    parts: List[str] = []
    used = 0
    for p in pins:
        chunk = p.strip()
        if not chunk:
            continue
        extra = len(chunk) + (1 if parts else 0)
        if used + extra > cap:
            break
        parts.append(chunk)
        used += extra
    return "\n".join(parts)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract / reinject constraint pins")
    ap.add_argument("--brief", default="", help="Brief text or @file path")
    ap.add_argument("--corrections", default="", help="Corrections text or @file / JSON list")
    ap.add_argument("--cap", type=int, default=DEFAULT_PIN_CAP)
    ap.add_argument("--json", action="store_true", help="Emit JSON {pins, reinjected}")
    args = ap.parse_args(argv)

    def load_text(s: str) -> str:
        if s.startswith("@") and len(s) > 1:
            return open(s[1:], encoding="utf-8").read()
        return s

    brief = load_text(args.brief)
    corr_raw = load_text(args.corrections)
    corrections: List[str] = []
    if corr_raw.strip().startswith("["):
        corrections = json.loads(corr_raw)
    elif corr_raw.strip():
        corrections = _lines(corr_raw)

    pins = extract_pins(brief, corrections)
    reinjected = reinject(pins, cap=args.cap)
    if args.json:
        json.dump({"pins": pins, "reinjected": reinjected}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(reinjected + ("\n" if reinjected else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
