#!/usr/bin/env python3
"""Kilo adapter stub for research-needed gate."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from research_gate import judge  # noqa: E402

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    snap = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    d, r = judge(snap.get("claim_text") or "", list(snap.get("known_docs") or []), "mock")
    out = {"decision": d, "reason_code": r, "gate_kind": "research", "wiring": "stub",
           "kilo_paths": ["~/.kilo", "%APPDATA%/Code/User/globalStorage/kilocode.kilo-code"]}
    print(json.dumps(out, indent=2) if args.json else f"{d}\t{r}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
