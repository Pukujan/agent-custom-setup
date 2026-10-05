#!/usr/bin/env python3
"""Fail-closed drift check for the multi-agent hotload pins.

``pins.json`` (next to the pack this script lives in) is the single source of
truth for the CGM / PCM / ACS pins the hotload pack advertises to adopters.
Every other file that records one of those pins is a *projection* and must
agree with the manifest. This script reads ``pins.json``, scans each declared
projection, and exits non-zero when a projection disagrees -- naming the
offending file and the two values (found vs expected).

Both shapes a pin takes are detected:

* the literal commit form -- full (``c069613ca8b3...``) or abbreviated
  (``c069613...``); and
* the version-string form -- the CGM version (``0.5.7``), the PCM CLI version
  (``CLI 0.6.0``) and the module-count word (``eight modules``).

A value listed under ``superseded`` fails even when the canonical value is
still present, so a file that carries both is caught. Code projections
(``scripts/*.py``) are read from their named pin constants rather than free
text, because their comments legitimately mention older versions.

Stdlib only. Run from anywhere:

    python modules/coordination/multi-agent-hotload/v0.1.0/scripts/check_pins.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = MODULE_ROOT / "pins.json"
# v0.1.0 -> multi-agent-hotload -> coordination -> modules -> repo root
REPO_ROOT = MODULE_ROOT.parents[3]

SHA_TOKEN_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
VERSION_RE = re.compile(r"\b\d+\.\d+\.\d+\b")
CLI_VERSION_RE = re.compile(r"\bCLI\b[^\n]{0,24}?(\d+\.\d+\.\d+)")
MODULE_COUNT_RE = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten)[\s-]+modules?\b",
    re.IGNORECASE,
)
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
# Projection keys are terse; map them onto the manifest's `pins` block.
KEY_ALIASES = {"acs": "acs_hotload_module"}
# Version commits are not copied into these files. stack-mesh.json is the
# requirement, and the hotloader reads it. A projection may still record the
# module count and the ACS module id.
CONSTANT_FILES: dict[str, dict[str, str]] = {}


def console_safe(text: str) -> str:
    """ASCII-safe for Windows cp1252 consoles (unicode punctuation crashes print)."""
    return text.replace("—", "-").replace("–", "-").replace("…", "...")


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def canonical(manifest: dict, key: str) -> str:
    """Resolve a dotted projection pin key against the manifest `pins` block."""
    parts = key.split(".")
    parts[0] = KEY_ALIASES.get(parts[0], parts[0])
    node: object = manifest["pins"]
    for part in parts:
        node = node[part]  # type: ignore[index]
    return str(node)


def pin_kind(key: str) -> str:
    if key.endswith(".commit"):
        return "commit"
    if key == "cgm.module_count":
        return "count"
    if key.endswith(".version") or key.endswith(".cli_version"):
        return "version"
    return "literal"


def short(value: str) -> str:
    return value[:7] + "..." if len(value) == 40 else value


def quoted(values) -> str:
    values = list(values)
    return ", ".join(f"'{v}'" for v in values) if values else "(not found)"


def check_manifest(manifest: object) -> list[str]:
    """Self-consistency: the manifest's own module count must match its list."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("pins"), dict):
        return ["pins.json: missing top-level 'pins' object"]
    errors: list[str] = []
    cgm = manifest["pins"].get("cgm", {})
    count, word, modules = cgm.get("module_count"), cgm.get("module_count_word"), cgm.get("modules")
    if isinstance(modules, list) and count is not None and len(modules) != count:
        errors.append(
            f"pins.json: cgm.module_count={count} but cgm.modules lists {len(modules)} ids"
        )
    if isinstance(word, str) and NUMBER_WORDS.get(word.lower()) != count:
        errors.append(
            f"pins.json: cgm.module_count_word={word!r} does not render cgm.module_count={count}"
        )
    return errors


def _revision_tokens(text: str) -> set[str]:
    """Hex tokens that plausibly are revisions (drop pure-numeric dates)."""
    return {t.lower() for t in SHA_TOKEN_RE.findall(text) if not t.isdigit()}


def _abbreviates(token: str, commit: str) -> bool:
    return commit.startswith(token) or token.startswith(commit)


def check_commit_pins(
    manifest: dict, file: str, text: str, keys: list[str], errors: list[str]
) -> None:
    """Presence per commit key, plus no foreign revision anywhere in the file."""
    commit_keys = sorted(k for k in keys if pin_kind(k) == "commit")
    if not commit_keys:
        return
    known = {k: canonical(manifest, k).lower() for k in commit_keys}
    tokens = _revision_tokens(text)
    foreign = sorted(t for t in tokens if not any(_abbreviates(t, c) for c in known.values()))

    if foreign:
        expected = ", ".join(short(known[k]) for k in commit_keys)
        for token in foreign:
            errors.append(f"{file}: commit drift expected {expected} but found '{token}'")
        return

    for key in commit_keys:
        value = known[key]
        if not any(t.startswith(value[:7]) for t in tokens):
            errors.append(f"{file}: {key} expected '{short(value)}' but found (not found)")
            continue
        for stale in manifest.get("superseded", {}).get(key, []):
            if str(stale).lower() in text.lower():
                errors.append(
                    f"{file}: {key} expected '{short(value)}' but found superseded '{stale}'"
                )


def check_version_pin(
    manifest: dict, file: str, text: str, key: str, errors: list[str]
) -> None:
    """Every token in the pinned version's family must equal the pinned version."""
    value = canonical(manifest, key)
    if key.endswith(".cli_version"):
        found = set(CLI_VERSION_RE.findall(text))
    else:
        family = value.rsplit(".", 1)[0] + "."
        found = {v for v in VERSION_RE.findall(text) if v.startswith(family)}
    wrong = sorted(found - {value})
    if value not in found:
        errors.append(f"{file}: {key} expected '{value}' but found {quoted(wrong)}")
    else:
        for token in wrong:
            errors.append(f"{file}: {key} expected '{value}' but found '{token}'")


def check_count_pin(manifest: dict, file: str, text: str, errors: list[str]) -> None:
    """The pinned count word must appear; a superseded count must not."""
    word = canonical(manifest, "cgm.module_count_word")
    count = canonical(manifest, "cgm.module_count")
    expected = f"{word} modules ({count})"
    if not re.search(rf"\b{re.escape(word)}[\s-]+modules?\b", text, re.IGNORECASE):
        found = sorted({m.group(1).lower() for m in MODULE_COUNT_RE.finditer(text)})
        errors.append(f"{file}: cgm.module_count expected '{expected}' but found {quoted(found)}")
        return
    for stale in manifest.get("superseded", {}).get("cgm.module_count", []):
        if re.search(rf"\b{re.escape(str(stale))}[\s-]+modules?\b", text, re.IGNORECASE):
            errors.append(
                f"{file}: cgm.module_count expected '{expected}' but found superseded "
                f"'{stale} modules'"
            )


def check_literal_pin(manifest: dict, file: str, text: str, key: str, errors: list[str]) -> None:
    value = canonical(manifest, key)
    if value not in text:
        errors.append(f"{file}: {key} expected '{value}' but found (not found)")


def check_constants(
    manifest: dict, file: str, text: str, mapping: dict[str, str], errors: list[str]
) -> None:
    """Verify a code file's named pin constants against the manifest."""
    for key, constant in mapping.items():
        value = canonical(manifest, key)
        match = re.search(
            rf"^{re.escape(constant)}\s*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE
        )
        if not match:
            errors.append(
                f"{file}: {key} constant {constant} expected '{short(value)}' "
                f"but found (missing)"
            )
            continue
        actual = match.group(1)
        if not (actual == value or value.startswith(actual) or actual.startswith(value)):
            errors.append(
                f"{file}: {key} constant {constant} expected '{short(value)}' "
                f"but found '{short(actual)}'"
            )


def check_file(manifest: dict, file: str, text: str, keys: list[str]) -> list[str]:
    """Return one drift message per pin key the file fails to match."""
    errors: list[str] = []
    constants = CONSTANT_FILES.get(file)
    if constants:
        mapping = {k: constants[k] for k in keys if k in constants}
        check_constants(manifest, file, text, mapping, errors)
        return errors
    check_commit_pins(manifest, file, text, keys, errors)
    for key in keys:
        kind = pin_kind(key)
        if kind == "version":
            check_version_pin(manifest, file, text, key, errors)
        elif kind == "count":
            check_count_pin(manifest, file, text, errors)
        elif kind == "literal":
            check_literal_pin(manifest, file, text, key, errors)
    return errors


def run(manifest_path: Path, root: Path) -> int:
    try:
        manifest = load_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"check_pins: FAIL\n  - {manifest_path.name} unreadable: {exc}")
        return 1

    problems = check_manifest(manifest)
    projections = manifest.get("projections", []) if isinstance(manifest, dict) else []
    if not isinstance(projections, list) or not projections:
        problems.append("pins.json: 'projections' must be a non-empty list")

    checked = 0
    for entry in projections:
        if not isinstance(entry, dict) or "file" not in entry:
            problems.append(f"pins.json: malformed projection entry: {entry!r}")
            continue
        rel = str(entry["file"])
        path = root / rel
        if not path.is_file():
            problems.append(f"{rel}: missing - projection file not found at {path}")
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            problems.append(f"{rel}: unreadable: {exc}")
            continue
        problems.extend(check_file(manifest, rel, text, list(entry.get("pins", []))))
        checked += 1

    if problems:
        print("check_pins: FAIL")
        for item in problems:
            for line in str(item).splitlines() or [str(item)]:
                print(f"  - {console_safe(line)}")
        return 1
    print(f"check_pins: OK ({checked} projections agree with {manifest_path.name})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    return run(args.manifest.resolve(), args.root.resolve())


if __name__ == "__main__":
    sys.exit(main())
