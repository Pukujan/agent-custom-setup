#!/usr/bin/env python3
"""Build a tiny gather package (pinned brief + corrections + proposed tool).

Enforces a character cap (default 8000). Never dump the full repo.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from pin_extract import extract_pins, reinject  # noqa: E402

DEFAULT_CHAR_CAP = 8000
TOKEN_CAP_NOTE = "~2-8k chars class; never full-repo dump; pin reinject ~47-token class OK"


def build_package(
    brief: str,
    corrections: List[str] | None,
    proposed_tool: Dict[str, str],
    char_cap: int = DEFAULT_CHAR_CAP,
    fixture_id: str | None = None,
) -> Dict[str, Any]:
    pins = extract_pins(brief, corrections or [])
    pin_budget = max(200, char_cap // 2)
    pinned = reinject(pins, cap=pin_budget)
    corr = list(corrections or [])
    corr_out: List[str] = []
    used = len(pinned)
    for c in corr:
        c = c.strip()
        if not c:
            continue
        if used + len(c) + 20 > char_cap - 400:
            break
        corr_out.append(c)
        used += len(c)

    name = str(proposed_tool.get("name", "")).strip()
    args_summary = str(proposed_tool.get("args_summary", "")).strip()
    max_args = max(64, min(1500, char_cap // 3))
    if len(args_summary) > max_args:
        args_summary = args_summary[: max_args - 3] + "..."

    pkg: Dict[str, Any] = {
        "pinned_brief": pinned or (brief[:pin_budget] if brief else ""),
        "corrections": corr_out,
        "proposed_tool": {"name": name, "args_summary": args_summary},
        "char_cap": char_cap,
        "token_cap_note": TOKEN_CAP_NOTE,
    }
    if fixture_id is not None:
        pkg["fixture_id"] = fixture_id

    def _size(p: Dict[str, Any]) -> int:
        return len(json.dumps(p, ensure_ascii=False))

    if _size(pkg) > char_cap:
        pkg["corrections"] = []
    if _size(pkg) > char_cap:
        overflow = _size(pkg) - char_cap
        pb = pkg["pinned_brief"]
        keep = max(0, len(pb) - overflow - 3)
        pkg["pinned_brief"] = (pb[:keep] + "...") if keep else ""
    if _size(pkg) > char_cap:
        overflow = _size(pkg) - char_cap
        args = pkg["proposed_tool"]["args_summary"]
        keep = max(0, len(args) - overflow - 3)
        pkg["proposed_tool"]["args_summary"] = (args[:keep] + "...") if keep else ""
    if _size(pkg) > char_cap:
        pkg["token_cap_note"] = "capped"
    if _size(pkg) > char_cap:
        raise ValueError(
            f"gather package exceeds char_cap={char_cap} even after trim ({_size(pkg)})"
        )
    return pkg


def package_size(pkg: Dict[str, Any]) -> int:
    return len(json.dumps(pkg, ensure_ascii=False))


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build gather package JSON")
    ap.add_argument("--brief", default="")
    ap.add_argument("--corrections-json", default="[]", help="JSON array of correction strings")
    ap.add_argument("--tool-name", required=True)
    ap.add_argument("--tool-args-summary", default="")
    ap.add_argument("--cap", type=int, default=DEFAULT_CHAR_CAP)
    ap.add_argument("--fixture-id", default=None)
    ap.add_argument("-o", "--output", default="-", help="Output path or - for stdout")
    args = ap.parse_args(argv)

    brief = args.brief
    if brief.startswith("@"):
        brief = Path(brief[1:]).read_text(encoding="utf-8")
    corrections = json.loads(args.corrections_json)
    pkg = build_package(
        brief=brief,
        corrections=corrections,
        proposed_tool={"name": args.tool_name, "args_summary": args.tool_args_summary},
        char_cap=args.cap,
        fixture_id=args.fixture_id,
    )
    out = json.dumps(pkg, indent=2, ensure_ascii=False) + "\n"
    if args.output == "-":
        sys.stdout.write(out)
    else:
        Path(args.output).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
