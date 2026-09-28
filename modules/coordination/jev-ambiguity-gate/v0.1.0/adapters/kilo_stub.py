#!/usr/bin/env python3
"""Kilo Code adapter stub for ambiguity gate.

Discovery paths (Windows):
  ~/.kilo/
  %APPDATA%/Code/User/globalStorage/kilocode.kilo-code/

Kilo does not yet expose a stable PrePrompt hook in ACS; this stub accepts a
JSON snapshot file and returns the same decisions as the CLI.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from ambiguity_gate import judge  # noqa: E402

def discover_kilo_roots() -> list[str]:
    home = Path.home()
    roots = [str(home / ".kilo")]
    gs = home / "AppData" / "Roaming" / "Code" / "User" / "globalStorage" / "kilocode.kilo-code"
    roots.append(str(gs))
    return [r for r in roots if Path(r).exists()]

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True, help="JSON with prompt/resume_context")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    d, r = judge(snap.get("prompt") or "", snap.get("resume_context") or "", "mock")
    out = {"decision": d, "reason_code": r, "gate_kind": "ambiguity", "kilo_roots": discover_kilo_roots(), "wiring": "stub"}
    print(json.dumps(out, indent=2) if args.json else f"{d}\t{r}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
