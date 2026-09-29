"""Hard-deny peer: catastrophic commands never reach Jev (FN=0 on holdouts)."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import auto_mode_policy as pol  # noqa: E402
from auto_mode_lane import run_auto_mode_pack  # noqa: E402

HOLD = ROOT / "fixtures" / "hard_deny"

def test_hard_deny_fixtures_fn0():
    false_neg = []
    for path in sorted(HOLD.glob("*.json")):
        fx = json.loads(path.read_text(encoding="utf-8"))
        v = pol.evaluate_bash(fx.get("command") or fx["proposed_tool"]["args_summary"])
        if v.decision != "deny" or v.layer != "hard_deny":
            false_neg.append({"id": fx["id"], "got": v})
    assert false_neg == [], false_neg

def test_hard_deny_never_needs_jev():
    for cmd in ["rm -rf /", "rm -rf ~", "git push --force origin main", "mkfs.ext4 /dev/sda1"]:
        v = pol.evaluate_bash(cmd)
        assert v.decision == "deny"
        assert v.layer == "hard_deny"
        assert v.decision != "needs_jev"

def test_safe_readonly_fast_path():
    for cmd in ["git status --short", "rg -n TODO src", "cat README.md", "ls -la"]:
        v = pol.evaluate_bash(cmd)
        assert v.decision == "allow", cmd
        assert v.layer == "safe_readonly"

def test_user_deny_beats_allow():
    v = pol.evaluate_bash("npm publish --access public", disallowed=["npm publish*"], allowed=["*"])
    assert v.decision == "deny"
    assert v.layer == "user_disallow"

def test_shell_control_blocks_allow_smuggle():
    v = pol.evaluate_bash("ls && rm -rf /", allowed=["ls*"])
    # allow pattern must not match through shell control; hard-deny may still catch rm
    assert v.decision == "deny"

def test_lane_hard_deny_without_live():
    pack = json.loads((HOLD / "hd-rm-root.json").read_text(encoding="utf-8"))
    out = run_auto_mode_pack(pack, use_live=False)
    assert out["decision"] == "deny"
    assert out["layer"] == "hard_deny"
    assert out["jev_ms"] == 0
