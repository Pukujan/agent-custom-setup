#!/usr/bin/env python3
"""Comparison-lane policy peer shaped like jomatsu/pi-jev-auto-mode.

Hard-deny runs BEFORE any Jev call. Adapted under MIT from
https://github.com/jomatsu/pi-jev-auto-mode (see THIRD_PARTY.md).
Not the live Claude/Kilo PreToolUse path — ACS jev-gate-pin stays default.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

SHELL_CONTROL = re.compile(r"[\r\n;&|<>$`()\\]")
PATH_GLOB = re.compile(r"[*?[\]{}]")

SAFE_COMMANDS = [
    "pwd", "cd*", "ls*", "tree*", "whoami", "hostname", "uname*", "date",
    "cat*", "bat*", "head*", "tail*", "less*", "wc*", "file*", "stat*",
    "realpath*", "readlink*", "basename*", "dirname*", "du*", "df*", "find*",
    "grep*", "rg*", "ag*", "jq*", "diff*", "cmp*", "sort*", "uniq*", "cut*",
    "column*", "nl*", "xxd*",
    "node --version*", "npm --version*", "python --version*", "python3 --version*",
    "uv --version*", "go version*", "cargo --version*", "gh --version*",
    "git status*", "git diff*", "git log*", "git show*", "git branch",
    "git remote", "git remote -v", "git blame*", "git shortlog*", "git describe*",
    "git rev-parse*", "git ls-files*", "git ls-tree*", "git worktree list*",
    "git stash list*", "git tag",
]

HARD_DENY: List[Tuple[str, re.Pattern]] = [
    ("recursive delete of a system or home root",
     re.compile(r"\brm\b[^\n;&|]*(?:--recursive|-[^\s;&|]*[rR][^\s;&|]*)[^\n;&|]*\s+[\"']?(?:/|~|\$HOME|\$\{HOME\}|/(?:Users|home|root|System|Applications|Library|etc|usr|var|bin|sbin|opt|private|Volumes))(?:[\"']?(?:\s|$)|/)", re.I)),
    ("unresolved recursive delete target",
     re.compile(r"\brm\b(?=[^\n;&|]*(?:--recursive|-[^\s;&|]*[rR][^\s;&|]*))(?=[^\n;&|]*(?:\$\(|\$\{|\$[A-Za-z_]|\$['\"]|~[A-Za-z]|[`*?[\]{}]|\{[^}]*,))[^\n;&|]*", re.I)),
    ("filesystem format or signature wipe", re.compile(r"\b(?:mkfs(?:\.[a-z0-9_+-]+)?|wipefs)\b", re.I)),
    ("disk device overwrite", re.compile(r"\bdd\b[^\n;&|]*\bof\s*=\s*[\"']?/dev/", re.I)),
    ("forced push to a protected branch",
     re.compile(r"\bgit\b[^\n;&|]*\bpush\b[^\n;&|]*(?:--force(?:-with-lease)?|-[^\s;&|]*f[^\s;&|]*)\b[^\n;&|]*\b(?:main|master|production|prod)\b", re.I)),
    ("forced push to a protected branch",
     re.compile(r"\bgit\b[^\n;&|]*\bpush\b[^\n;&|]*\b(?:main|master|production|prod)\b[^\n;&|]*(?:--force(?:-with-lease)?|-[^\s;&|]*f[^\s;&|]*)\b", re.I)),
]

DANGEROUS: List[Tuple[str, re.Pattern]] = [
    ("recursive/forced rm", re.compile(r"\brm\b(?=[^\n;&|]*\s-(?:[^\s;&|]*[rR][^\s;&|]*[fF]?|[^\s;&|]*[fF][^\s;&|]*[rR])\b|[^\n;&|]*\s--recursive\b)", re.I)),
    ("remove Git metadata", re.compile(r"\brm\b[^\n;&|]*\s(?:\.git|\.git/|['\"]\.git['\"])", re.I)),
    ("find delete", re.compile(r"\bfind\b[^\n;&|]*\s-delete\b", re.I)),
    ("package execution or publish", re.compile(r"\b(?:npm|pnpm|yarn|bun|pip|pip3|uv|poetry|cargo|gem|go|brew|apt(?:-get)?|dnf|pacman)\b[^\n;&|]*\b(?:exec|run|dlx|publish)\b", re.I)),
    ("package runner", re.compile(r"\b(?:npx|pnpm\s+dlx|yarn\s+dlx|bunx|pipx|uvx)\b", re.I)),
    ("sudo", re.compile(r"\bsudo\b", re.I)),
    ("git reset hard", re.compile(r"\bgit\b[^\n;&|]*\breset\b[^\n;&|]*\s--hard\b", re.I)),
    ("git force push", re.compile(r"\bgit\b[^\n;&|]*\bpush\b[^\n;&|]*\s--(?:force|force-with-lease|mirror)\b", re.I)),
    ("git force push", re.compile(r"\bgit\b[^\n;&|]*\bpush\b[^\n;&|]*\s-[^\s;&|]*f[^\s;&|]*\b", re.I)),
    ("downloaded script execution", re.compile(r"\b(?:curl|wget)\b[^\n;&|]*(?:\|\s*(?:sh|bash|zsh)\b|\b(?:sh|bash|zsh)\s*<\s*\()", re.I)),
    ("network upload of local data", re.compile(r"\b(?:curl|wget)\b[^\n;&|]*(?:\s-d\s*@|\s--data(?:-binary|-raw|-urlencode)?\s*@|\s-T\s|\s--upload-file\b|\s-F\s[^\s;&|]*=@|\s--form\s[^\s;&|]*=@)", re.I)),
    ("file transfer to a remote host", re.compile(r"\b(?:scp|rsync|sftp)\b", re.I)),
    ("reads a credential file", re.compile(r"\b(?:cat|bat|less|more|head|tail|xxd|base64|grep|rg)\b[^\n;&|]*(?:\.ssh/|id_rsa|id_ed25519|id_ecdsa|\.aws/|\.gnupg|\.npmrc|credentials|\.env\b(?!\.(?:example|sample|template)))", re.I)),
    ("selfhost fish-speech", re.compile(r"(fish-speech|run_selfhost|selfhost_server)", re.I)),
]

def _glob_to_re(pattern: str) -> re.Pattern:
    src = "^"
    for ch in pattern:
        if ch == "*":
            src += r"[\s\S]*"
        elif ch == "?":
            src += r"[\s\S]"
        else:
            src += re.escape(ch)
    return re.compile(src + "$", re.I)

def matches_command_pattern(command: str, pattern: str, allow_shell_control: bool) -> bool:
    p = pattern.strip()
    if not p or "\n" in p or "\r" in p:
        return False
    if not allow_shell_control and SHELL_CONTROL.search(command):
        return False
    return bool(_glob_to_re(p).match(command.strip()))

def hard_deny_reasons(command: str) -> List[str]:
    out, seen = [], set()
    for name, pat in HARD_DENY:
        if pat.search(command) and name not in seen:
            seen.add(name); out.append(name)
    return out

def dangerous_reasons(command: str) -> List[str]:
    out, seen = [], set()
    for name, pat in DANGEROUS:
        if pat.search(command) and name not in seen:
            seen.add(name); out.append(name)
    return out

def is_safe_command(command: str) -> bool:
    return any(matches_command_pattern(command, p, False) for p in SAFE_COMMANDS)

@dataclass
class PolicyVerdict:
    decision: str  # allow|deny|escalate|needs_jev
    layer: str
    reasons: List[str]

def evaluate_bash(command: str, *, disallowed: Sequence[str] = (), allowed: Sequence[str] = ()) -> PolicyVerdict:
    """Deterministic envelope. needs_jev means caller may call Jev."""
    hd = hard_deny_reasons(command)
    if hd:
        return PolicyVerdict("deny", "hard_deny", hd)
    for pat in disallowed:
        if matches_command_pattern(command, pat, True):
            return PolicyVerdict("deny", "user_disallow", [pat])
    for pat in allowed:
        if matches_command_pattern(command, pat, False):
            return PolicyVerdict("allow", "user_allow", [pat])
    if is_safe_command(command):
        return PolicyVerdict("allow", "safe_readonly", ["safe_command"])
    dang = dangerous_reasons(command)
    if dang:
        return PolicyVerdict("needs_jev", "dangerous", dang)
    return PolicyVerdict("needs_jev", "default", ["unclassified"])
