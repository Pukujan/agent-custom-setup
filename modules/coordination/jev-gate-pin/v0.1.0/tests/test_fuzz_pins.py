from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pin_extract import extract_pins, reinject  # noqa: E402

def test_fuzz_duplicate_and_cap():
    lines = ["MUST use hosted API"] * 20 + ["noise"] * 20
    pins = extract_pins("\n".join(lines), lines)
    assert len(pins) == 1
    assert len(reinject(pins, cap=10)) <= 10

def test_fuzz_mixed_separators():
    text = "MUST use hosted\r\nMUST NOT self-host\n\nAPI key path configs/.env"
    pins = extract_pins(text, [])
    assert len(pins) >= 2
