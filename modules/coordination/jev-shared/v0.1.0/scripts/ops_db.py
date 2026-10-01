#!/usr/bin/env python3
"""Shim: load canonical ops-db scripts without circular self-import."""
from __future__ import annotations
import importlib.util
from pathlib import Path

_OPS = Path(__file__).resolve().parents[3] / "ops-db" / "v0.1.0" / "scripts" / "ops_db.py"
_spec = importlib.util.spec_from_file_location("acs_ops_db_canonical", _OPS)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)

append_gate_event = _mod.append_gate_event
append_claim_snapshot = _mod.append_claim_snapshot
append_issue_snapshot = _mod.append_claim_snapshot
as_of_gate_events = _mod.as_of_gate_events
as_of_claim_snapshots = _mod.as_of_claim_snapshots
connect = _mod.connect
default_ops_db_path = _mod.default_ops_db_path
SCHEMA = _mod.SCHEMA
