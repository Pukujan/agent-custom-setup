"""Pin extract always runs before mock judge; empty pins still gather."""
from __future__ import annotations
import sys
from pathlib import Path
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from pin_extract import extract_pins  # noqa: E402
from gather import build_package  # noqa: E402
from gate import mock_judge  # noqa: E402

def test_pin_then_judge_on_fish_block():
    brief = "MUST use hosted fish.audio. Do NOT self-host."
    corr = ["MUST NOT clone fish-speech"]
    pins = extract_pins(brief, corr)
    assert pins
    pkg = build_package(brief=brief, corrections=corr, proposed_tool={"name": "Bash", "args_summary": "git clone fish-speech && pip install -e ."})
    assert pkg["pinned_brief"]
    d, r = mock_judge(pkg)
    assert d == "deny"

def test_gather_without_pins_still_packages_tool():
    pkg = build_package(brief="hello", corrections=[], proposed_tool={"name": "Read", "args_summary": "foo.py"})
    assert pkg["proposed_tool"]["name"] == "Read"
    d, _ = mock_judge(pkg)
    assert d == "allow"
