#!/usr/bin/env python3
"""Deterministically derive eval variants from the live README (no manual copies).

Usage: python3 evals/build_variants.py
Writes: evals/variants/{current,stub,reordered,bold_stripped,claim_removed}.md
Transforms are identity-preserving except where the metamorphic class says so.
Derived from the pinned CGM test design (docs/README_QUALITY_TDD.md M-01/M-04/M-09).
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VDIR = ROOT / "evals" / "variants"
VDIR.mkdir(parents=True, exist_ok=True)

readme = (ROOT / "README.md").read_text(encoding="utf-8")

# stub (differential "before"): the placeholder README on main at 1c44c8d.
stub = subprocess.run(
    ["git", "-C", str(ROOT), "show", "1c44c8d2f25cb71e8acb20253e2cc26cd682af81:README.md"],
    capture_output=True, text=True, check=True,
).stdout


def reversed_section_bullets(text: str, header: str) -> str:
    """M-01: reverse bullet units (blank line + '- ' block + continuations)."""
    lines = text.splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if l.strip() == f"## {header}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    units: list[list[str]] = []
    pending: list[str] = []
    i = start + 1
    while i < end:
        if lines[i].startswith("- "):
            block = pending + [lines[i]]
            pending = []
            i += 1
            while i < end and lines[i].startswith("  "):
                block.append(lines[i])
                i += 1
            units.append(block)
        else:
            pending.append(lines[i])
            i += 1
    assert len(units) >= 2, f"section {header!r} has no multi-bullet list"
    # trailing non-bullet lines stay in place; every other line lives in exactly one unit
    return "".join(lines[: start + 1]) + "".join(b for u in reversed(units) for b in u) + "".join(pending) + "".join(lines[end:])

def reversed_table_rows(text: str, header_prefix: str) -> str:
    """M-01: reverse body rows of a pipe table (row identities preserved)."""
    lines = text.splitlines(keepends=True)
    out, i, hit = [], 0, False
    while i < len(lines):
        if lines[i].startswith(header_prefix):
            hit = True
            out.append(lines[i]); out.append(lines[i + 1]); i += 2
            body = []
            while i < len(lines) and lines[i].startswith("|"):
                body.append(lines[i]); i += 1
            out.extend(reversed(body))
            continue
        out.append(lines[i]); i += 1
    assert hit, f"no table starting {header_prefix!r}"
    return "".join(out)


reordered = reversed_table_rows(
    reversed_section_bullets(readme, "What you can make or use"), "| Claim | Status"
)
assert reordered != readme, "M-01 transform matched nothing"
assert sorted(readme.splitlines()) == sorted(reordered.splitlines()), "M-01 changed content lines"

# M-09: strip markdown bold markers only; line content otherwise identical.
bold_stripped = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", readme)
assert bold_stripped != readme, "M-09 found no bold anchors"
perline = [re.sub(r"\*\*([^*\n]+)\*\*", r"\1", l) for l in readme.splitlines()]
assert perline == bold_stripped.splitlines(), "M-09 changed non-bold content"

# M-04 evidence removal: the pending-merge module claim's four carriers
# (status-at-a-glance line, bullet, evidence-table row, Try-it paragraph) all
# contain "oh-my-pi" (case-sensitive); the filter must leave no residual
# citation and must not touch unrelated claims (asserts enforce both ways).
claim_removed = "".join(l for l in readme.splitlines(keepends=True) if "oh-my-pi" not in l)
assert claim_removed != readme, "M-04 transform matched nothing"
for token in ("oh-my-pi", "0b29fdc", "PR #4", "pull request #4"):
    assert token not in claim_removed, f"M-04: residual carrier {token!r} survives"
for keep in ("Claude Code", "planned", "1c44c8d"):
    assert keep in claim_removed, f"M-04: removed unrelated claim/evidence {keep!r}"

for name, content in {
    "current.md": readme,
    "stub.md": stub,
    "reordered.md": reordered,
    "bold_stripped.md": bold_stripped,
    "claim_removed.md": claim_removed,
}.items():
    (VDIR / name).write_text(content, encoding="utf-8")
    print(f"wrote evals/variants/{name} ({len(content)} bytes)")
