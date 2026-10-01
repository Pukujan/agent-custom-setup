"""Pin fuzz + research-vs-human (checklist fallback) tests."""
from __future__ import annotations
import json, sys
from pathlib import Path

PIN = Path(__file__).resolve().parents[3] / "jev-gate-pin" / "v0.1.0" / "scripts"
RES = Path(__file__).resolve().parents[3] / "jev-research-gate" / "v0.1.0" / "scripts"
sys.path.insert(0, str(PIN))
sys.path.insert(0, str(RES))
from pin_extract import extract_pins, reinject, is_pin_line  # noqa: E402
from research_gate import mock_judge  # noqa: E402

def test_pin_fuzz_whitespace_and_case():
    brief = "  must use HOSTED fish.audio API  \n\nDo Not Self-Host\nnoise line\nMUST NOT clone fish-speech"
    pins = extract_pins(brief, ["  MUST use hosted fish.audio API "])
    assert any("hosted" in p.lower() for p in pins)
    assert any("must not" in p.lower() or "self" in p.lower() for p in pins)
    # reinject never grows unbounded
    text = reinject(pins * 50, cap=200)
    assert len(text) <= 200

def test_pin_never_empty_when_must_present():
    assert extract_pins("MUST keep API path configs/.env", [])

def test_non_pin_lines_dropped():
    pins = extract_pins("hello world\nrandom chatter\nTODO later", [])
    assert pins == []

def test_research_yes_external_no_docs():
    d, r = mock_judge("Bump Claude Code hooks API and read official docs", [])
    assert d == "yes"

def test_research_no_local_pytest():
    d, r = mock_judge("Add unit test pytest in-repo fixture only", ["README.md"])
    assert d == "no"

def test_research_insufficient_empty_uses_checklist_fallback_contract():
    d, r = mock_judge("", [])
    assert d == "insufficient"
    # caller maps insufficient → #14 checklist (documented on research_gate result)
