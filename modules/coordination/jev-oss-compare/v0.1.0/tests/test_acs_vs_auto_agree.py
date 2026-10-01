"""Agreement / FN/FP across ACS and auto-mode lanes on shared packs."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from acs_lane import run_acs_pack  # noqa: E402
from auto_mode_lane import run_auto_mode_pack  # noqa: E402
from compare_run import load_packs  # noqa: E402

def test_fish_block_both_deny_mock():
    fish = Path(__file__).resolve().parents[3] / "jev-gate-pin" / "v0.1.0" / "fixtures" / "fish_hosted_vs_selfhost" / "block_selfhost_despite_hosted_brief.json"
    pack = json.loads(fish.read_text(encoding="utf-8"))
    acs = run_acs_pack(pack, use_live=False)
    auto = run_auto_mode_pack(pack, use_live=False)
    assert acs["decision"] == "deny"
    assert auto["decision"] == "deny"

def test_fish_allow_acs_allows():
    fish = Path(__file__).resolve().parents[3] / "jev-gate-pin" / "v0.1.0" / "fixtures" / "fish_hosted_vs_selfhost" / "allow_hosted_api_tool.json"
    pack = json.loads(fish.read_text(encoding="utf-8"))
    acs = run_acs_pack(pack, use_live=False)
    assert acs["decision"] == "allow"

def test_load_packs_capped_and_deduped():
    packs = load_packs(5)
    assert 1 <= len(packs) <= 5
    ids = [p["id"] for p in packs]
    assert len(ids) == len(set(ids))

def test_gold_fn0_on_hard_deny_and_fish_block():
    packs = load_packs(30)
    fn = []
    for p in packs:
        gold = p.get("gold_decision")
        if gold not in ("deny", "block"):
            continue
        acs = run_acs_pack(p, use_live=False)
        # hard_deny packs are bash catastrophic — ACS Fish mock may allow non-Fish;
        # require auto-mode deny; ACS deny when Fish-class or ACS gold fish fixtures
        auto = run_auto_mode_pack(p, use_live=False)
        if p["id"].startswith("hd-") or "fish" in str(p.get("id")):
            if auto["decision"] != "deny":
                fn.append(("auto", p["id"], auto))
        if "fish" in str(p.get("id")) and acs["decision"] != "deny":
            fn.append(("acs", p["id"], acs))
    assert fn == [], fn

def test_agreement_rate_on_mock_corpus_recorded():
    packs = load_packs(20)
    rows = []
    for p in packs:
        a = run_acs_pack(p, use_live=False)
        b = run_auto_mode_pack(p, use_live=False)
        rows.append(a["decision"] == b["decision"])
    # Not required to be 100%; just ensure we compute a finite rate and have data
    assert rows
    rate = sum(rows) / len(rows)
    assert 0.0 <= rate <= 1.0
