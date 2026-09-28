from __future__ import annotations
import ast
from pathlib import Path

GATES = [
    Path(__file__).resolve().parents[3] / "jev-ambiguity-gate" / "v0.1.0" / "scripts" / "ambiguity_gate.py",
    Path(__file__).resolve().parents[3] / "jev-research-gate" / "v0.1.0" / "scripts" / "research_gate.py",
    Path(__file__).resolve().parents[3] / "jev-gate-pin" / "v0.1.0" / "scripts" / "gate.py",
]

FORBIDDEN = {"numpy", "embed_scan", "cosine", "sentence_transformers"}

def test_gate_scripts_have_no_embed_imports():
    for path in GATES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    names.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        bad = names & FORBIDDEN
        assert not bad, f"{path.name} imports forbidden hot-path modules: {bad}"

