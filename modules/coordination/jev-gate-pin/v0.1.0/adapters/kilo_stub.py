#!/usr/bin/env python3
"""Kilo adapter stub for jev-gate-pin (tool time)."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from gather import build_package  # noqa: E402
from gate import judge_package  # noqa: E402

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", help="gather package JSON")
    ap.add_argument("--fixture", help="fish fixture JSON")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.fixture:
        fx = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        pkg = build_package(brief=fx.get("brief") or "", corrections=list(fx.get("corrections") or []),
                            proposed_tool=dict(fx.get("proposed_tool") or {}), fixture_id=fx.get("id"))
    else:
        pkg = json.loads(Path(args.package).read_text(encoding="utf-8"))
    d, r = judge_package(pkg, "mock")
    out = {"decision": d, "reason_code": r, "gate_kind": "tool_pin", "wiring": "stub",
           "kilo_paths": ["~/.kilo", "%APPDATA%/Code/User/globalStorage/kilocode.kilo-code"]}
    print(json.dumps(out, indent=2) if args.json else f"{d}\t{r}")
    return 0 if d == "allow" else 2

if __name__ == "__main__":
    raise SystemExit(main())
