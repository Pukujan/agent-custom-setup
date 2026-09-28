"""Post-run jev-gate stub + appendable multi-page HTML report."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "adapters"))
import jev_gate_post_run_stub as stub  # noqa: E402
from html_report import append_run, build_shell  # noqa: E402

def test_post_run_mock_pass():
    r = stub.mock_eval("tests pass\nok", "Tests pass", 0.7)
    assert r["passed"] is True

def test_post_run_mock_fail_on_secretish():
    r = stub.mock_eval("leaked sk-test-ABCDEFGH", "No secrets", 0.7)
    assert r["passed"] is False

def test_html_append_newest_first(tmp_path):
    report = tmp_path / "jev-oss-compare.html"
    append_run(report, {"run_id": "A", "started_at": "t1", "agree": 1, "disagree": 0, "fn_vs_gold": 0, "fp_vs_gold": 0, "live": False, "n_packs": 1, "agree_pct": 100.0, "p50_jev_ms": 10, "p95_jev_ms": 20},
               [{"id": "p1", "gold": "deny", "acs_decision": "deny", "acs_layer": "mock", "auto_decision": "deny", "auto_layer": "hard_deny", "agree": True, "acs_ms": 1, "auto_ms": 1, "jev_ms": 0}])
    append_run(report, {"run_id": "B", "started_at": "t2", "agree": 0, "disagree": 1, "fn_vs_gold": 0, "fp_vs_gold": 0, "live": False, "n_packs": 1, "agree_pct": 0.0, "p50_jev_ms": 11, "p95_jev_ms": 21},
               [{"id": "p2", "gold": "allow", "acs_decision": "allow", "acs_layer": "mock", "auto_decision": "deny", "auto_layer": "x", "agree": False, "acs_ms": 1, "auto_ms": 1, "jev_ms": 0}])
    text = report.read_text(encoding="utf-8")
    assert 'data-run-id="B"' in text and 'data-run-id="A"' in text
    assert text.index('data-run-id="B"') < text.index('data-run-id="A"')
    assert "How we compared" in text
    assert "ADAPT_PATTERN" in text or "What we kept" in text
    for page in ("overview", "method", "pipeline", "results", "charts", "disagree", "append"):
        assert f'data-page="{page}"' in text
    assert "mermaid" in text
    assert "agreeChart" in text and "latChart" in text
    assert "Append next run" in text or "append" in text

def test_shell_has_hsw_concrete_lede():
    shell = build_shell()
    assert "Fish" in shell
    assert "delve" not in shell.lower()
    assert "showcase" not in shell.lower()
    assert "Packs compared" in shell or "No compare run" in shell
