"""Unit tests for pin extract + gather caps."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = MODULE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from gather import DEFAULT_CHAR_CAP, build_package, package_size  # noqa: E402
from pin_extract import extract_pins, reinject  # noqa: E402
from log_event import make_event, redact  # noqa: E402


BRIEF = (
    "Fish voice lab: MUST use Fish Audio hosted API (fish.audio). "
    "Do NOT self-host. Key path: configs/.env FISH_API_KEY. Prefer free model id."
)
CORRECTIONS = [
    "MUST use hosted fish.audio API",
    "MUST NOT pip install fish-speech for self-host",
    "Ignore this unrelated note about lunch",
]


def test_extract_pins_keeps_constraint_lines():
    pins = extract_pins(BRIEF, CORRECTIONS)
    joined = "\n".join(pins).lower()
    assert "hosted" in joined or "must" in joined
    assert any("fish.audio" in p.lower() or "hosted" in p.lower() for p in pins)
    # Unrelated lunch line should not appear
    assert not any("lunch" in p.lower() for p in pins)


def test_reinject_respects_cap():
    pins = ["MUST use hosted API"] * 50
    out = reinject(pins, cap=80)
    assert len(out) <= 80
    assert "MUST use hosted API" in out


def test_gather_package_under_cap():
    pkg = build_package(
        brief=BRIEF,
        corrections=CORRECTIONS,
        proposed_tool={
            "name": "Bash",
            "args_summary": "pip install fish-speech && run selfhost",
        },
        char_cap=DEFAULT_CHAR_CAP,
        fixture_id="unit-1",
    )
    assert package_size(pkg) <= DEFAULT_CHAR_CAP
    assert pkg["proposed_tool"]["name"] == "Bash"
    assert pkg["char_cap"] == DEFAULT_CHAR_CAP
    assert "token_cap_note" in pkg


def test_gather_package_tiny_cap():
    pkg = build_package(
        brief=BRIEF * 20,
        corrections=CORRECTIONS * 20,
        proposed_tool={"name": "Bash", "args_summary": "x" * 2000},
        char_cap=1500,
    )
    assert package_size(pkg) <= 1500


def test_redact_secrets():
    assert "[REDACTED]" in redact("api_key=sk-abc123456789012345")
    assert "[REDACTED]" in redact("Authorization: Bearer deadbeefdeadbeefdeadbeefdeadbeef")
    ev = make_event(
        decision="deny",
        tool_name="Bash",
        reason_code="test",
        notes="token=supersecretvalue123",
    )
    assert "supersecretvalue123" not in json.dumps(ev)
