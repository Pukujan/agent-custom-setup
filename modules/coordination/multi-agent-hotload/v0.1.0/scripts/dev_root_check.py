#!/usr/bin/env python3
"""Check that the dev root holds only one main checkout per repo.

The dev root (``D:\\development`` on Windows, ``~/development`` elsewhere;
override with ``ACS_DEV_ROOT`` or ``--dev-root``) is where an operator keeps
the primary checkout of each repo they work on. Everything else an agent
creates while working -- linked git worktrees, pinned dependency clones,
scratch probes, throwaway copies, tool caches -- belongs in the per-user ACS
cache instead:

* Windows: ``%LOCALAPPDATA%\\acs\\{deps,scratch,worktrees}``
* macOS / Linux: ``$XDG_CACHE_HOME/acs/...`` (default ``~/.cache/acs/...``)

Override the cache root with ``ACS_CACHE_DIR``.

This script looks at every top-level entry of the dev root and reports each one
that is not a single primary git checkout:

* ``not_git``            -- a plain directory with no ``.git``
* ``dot_or_dep_folder``  -- a dot- or underscore-folder such as ``.scratch`` or ``_deps``
* ``stray_file``         -- a loose file at the top level
* ``linked_worktree``    -- a checkout whose ``.git`` is a file (``git worktree add``)
* ``duplicate_clone``    -- a second checkout of a remote that already has a primary
* ``registered_worktree``-- a worktree registered by a primary checkout whose path is
  under the dev root (nested inside a repo, or a stale registration)

It prints a JSON report and exits 1 when it finds anything, 0 when the root is
clean, and 2 when the dev root does not exist.

``--clean`` plans a fix for each finding. It is a dry run unless ``--yes`` is
also given. It never touches a git repo (or a folder containing one) that has
uncommitted changes, commits not on any remote, or stashes. Safe linked
worktrees are removed with ``git worktree remove`` + ``git worktree prune``;
other safe entries are moved into the cache (``scratch/`` or ``deps/``), and
top-level tool caches such as ``node_modules`` are removed.

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CACHE_DIR_NAMES = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    ".pnpm-store",
}
# OS litter that is not worth flagging.
IGNORED_NAMES = {"desktop.ini", "Thumbs.db", ".DS_Store"}
CACHE_SUBDIRS = ("deps", "scratch", "worktrees")


class DevRootViolation(RuntimeError):
    """Raised when a write that belongs in the cache targets the dev root."""


# ---------------------------------------------------------------- locations


def default_dev_root() -> Path:
    env = os.environ.get("ACS_DEV_ROOT")
    if env:
        return Path(env).expanduser()
    if os.name == "nt":
        return Path("D:/development")
    return Path.home() / "development"


def default_cache_dir() -> Path:
    env = os.environ.get("ACS_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "acs"
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "acs"


def cache_subdir(kind: str, cache_dir: Path | None = None) -> Path:
    if kind not in CACHE_SUBDIRS:
        raise ValueError(f"unknown cache kind {kind!r}; expected one of {CACHE_SUBDIRS}")
    return (cache_dir or default_cache_dir()) / kind


def _norm(path: Path) -> str:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = path.expanduser().absolute()
    return os.path.normcase(str(resolved))


def is_inside(path: Path, root: Path) -> bool:
    """True when ``path`` is ``root`` or anywhere below it."""
    p, r = _norm(path), _norm(root)
    return p == r or p.startswith(r.rstrip("\\/") + os.sep)


def is_primary_checkout_path(path: Path, dev_root: Path) -> bool:
    """True for a direct child of the dev root whose ``.git`` is a directory."""
    try:
        parent_ok = _norm(path.expanduser().resolve().parent) == _norm(dev_root)
    except OSError:
        return False
    return parent_ok and (path / ".git").is_dir()


def ensure_outside_dev_root(path: Path, dev_root: Path | None = None) -> Path:
    """Return ``path`` if it is outside the dev root, else raise DevRootViolation.

    Use this before writing dependency clones, scratch work, worktrees or caches.
    """
    root = dev_root if dev_root is not None else default_dev_root()
    if is_inside(path, root):
        raise DevRootViolation(
            f"refusing to write {path} inside the dev root {root}; dependency clones, "
            f"scratch, worktrees and caches belong under {default_cache_dir()}"
        )
    return path


# ---------------------------------------------------------------- git helpers


def _git(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return 127, str(exc)
    return proc.returncode, (proc.stdout or "").strip()


def git_remote(path: Path) -> str | None:
    code, out = _git(["-C", str(path), "remote", "get-url", "origin"])
    return out if code == 0 and out else None


def normalize_remote(url: str) -> str:
    u = url.strip().lower().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    if u.startswith("git@") and ":" in u:
        host, _, rest = u[4:].partition(":")
        u = f"{host}/{rest}"
    for prefix in ("https://", "http://", "ssh://git@", "ssh://", "git://"):
        if u.startswith(prefix):
            u = u[len(prefix):]
            break
    if "@" in u.split("/", 1)[0]:
        u = u.split("@", 1)[1]
    return u


def registered_worktrees(repo: Path) -> list[Path]:
    """Linked worktrees registered by ``repo`` (excludes the main worktree)."""
    code, out = _git(["-C", str(repo), "worktree", "list", "--porcelain"])
    if code != 0:
        return []
    paths = [Path(line[len("worktree "):]) for line in out.splitlines() if line.startswith("worktree ")]
    return [p for p in paths if _norm(p) != _norm(repo)]


def git_work_status(path: Path, *, head_only: bool = False) -> dict:
    """Uncommitted changes, commits not on any remote, and stashes for one repo.

    ``head_only`` limits the unpushed check to the checked-out HEAD, which is what
    matters for a linked worktree (its siblings share the branch list).
    """
    status: dict = {"path": str(path)}
    code, out = _git(["-C", str(path), "status", "--porcelain"])
    status["dirty"] = [ln for ln in out.splitlines() if ln.strip()] if code == 0 else ["<git status failed>"]
    # Commits on any local branch or on HEAD that no remote-tracking ref contains.
    revs = ["HEAD"] if head_only else ["HEAD", "--branches"]
    code, out = _git(["-C", str(path), "log", "--oneline", *revs, "--not", "--remotes"])
    if code != 0 and not head_only:
        # An empty repo has no HEAD; fall back to branches only.
        code, out = _git(["-C", str(path), "log", "--oneline", "--branches", "--not", "--remotes"])
    status["unpushed"] = [ln for ln in out.splitlines() if ln.strip()] if code == 0 else []
    code, out = _git(["-C", str(path), "stash", "list"])
    status["stashes"] = [ln for ln in out.splitlines() if ln.strip()] if code == 0 else []
    status["has_work"] = bool(status["dirty"] or status["unpushed"] or status["stashes"])
    return status


def nested_git_repos(root: Path, max_depth: int = 4) -> list[Path]:
    """Git checkouts at or below ``root`` (skipping caches), for non-git folders."""
    found: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        cur, depth = stack.pop()
        if (cur / ".git").exists():
            found.append(cur)
            continue
        if depth >= max_depth:
            continue
        try:
            children = [c for c in cur.iterdir() if c.is_dir() and not c.is_symlink()]
        except OSError:
            continue
        for child in children:
            if child.name in CACHE_DIR_NAMES:
                continue
            stack.append((child, depth + 1))
    return found


# ---------------------------------------------------------------- scan


def _finding(path: Path, kind: str, detail: str, **extra) -> dict:
    item = {"name": path.name, "path": str(path), "kind": kind, "detail": detail}
    item.update(extra)
    return item


def scan(dev_root: Path, *, allow: set[str] | None = None) -> dict:
    """Return the report dict for ``dev_root`` (does not change anything)."""
    allow = {a.lower() for a in (allow or set())}
    dev_root = dev_root.expanduser()
    findings: list[dict] = []
    primaries: dict[str, list[Path]] = {}
    primary_list: list[Path] = []

    entries = sorted(dev_root.iterdir(), key=lambda p: p.name.lower())
    for entry in entries:
        name = entry.name
        if name in IGNORED_NAMES or name.lower() in allow:
            continue
        if not entry.is_dir():
            findings.append(_finding(entry, "stray_file", "loose file at the top of the dev root"))
            continue
        git_marker = entry / ".git"
        if git_marker.is_file():
            findings.append(
                _finding(entry, "linked_worktree", ".git is a file: this is a linked worktree, not a main checkout")
            )
            continue
        if not git_marker.is_dir():
            if name in CACHE_DIR_NAMES:
                findings.append(_finding(entry, "cache_folder", "tool cache at the top of the dev root"))
            elif name.startswith((".", "_")):
                findings.append(_finding(entry, "dot_or_dep_folder", "dot/underscore folder (scratch, deps or cache)"))
            else:
                findings.append(_finding(entry, "not_git", "plain folder with no .git"))
            continue
        if name.startswith((".", "_")):
            findings.append(_finding(entry, "dot_or_dep_folder", "git checkout hidden in a dot/underscore folder"))
            continue
        remote = git_remote(entry)
        key = normalize_remote(remote) if remote else f"<no-remote>:{_norm(entry)}"
        primaries.setdefault(key, []).append(entry)
        primary_list.append(entry)

    # Duplicate clones: keep the one named after the remote (else the first by name).
    for key, paths in primaries.items():
        if len(paths) < 2:
            continue
        repo_name = key.rsplit("/", 1)[-1]
        keep = next((p for p in paths if p.name.lower() == repo_name), paths[0])
        for p in paths:
            if p is keep:
                continue
            findings.append(
                _finding(
                    p,
                    "duplicate_clone",
                    f"second checkout of {key}; primary is {keep.name}",
                    remote=key,
                    primary=str(keep),
                )
            )
            primary_list.remove(p)

    # Worktrees registered by primaries that live under the dev root.
    seen = {_norm(Path(f["path"])) for f in findings}
    for repo in primary_list:
        for wt in registered_worktrees(repo):
            if not is_inside(wt, dev_root):
                continue
            n = _norm(wt)
            if n in seen:
                for f in findings:
                    if _norm(Path(f["path"])) == n:
                        f["registered_by"] = str(repo)
                continue
            seen.add(n)
            exists = wt.exists()
            findings.append(
                _finding(
                    wt,
                    "registered_worktree",
                    "worktree registered under the dev root" + ("" if exists else " (path missing; prunable)"),
                    registered_by=str(repo),
                    exists=exists,
                )
            )

    return {
        "dev_root": str(dev_root),
        "cache_dir": str(default_cache_dir()),
        "ok": not findings,
        "primary_checkouts": [p.name for p in primary_list],
        "findings": findings,
    }


# ---------------------------------------------------------------- clean


def _unique_target(base: Path, name: str) -> Path:
    target = base / name
    if not target.exists():
        return target
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return base / f"{name}-{stamp}"


def plan_clean(report: dict, cache_dir: Path) -> list[dict]:
    """Decide what to do with each finding. Pure apart from read-only git calls."""
    dev_root = Path(report["dev_root"])
    actions: list[dict] = []
    for f in report["findings"]:
        path = Path(f["path"])
        kind = f["kind"]
        act: dict = {"path": str(path), "kind": kind}
        if kind in ("linked_worktree", "registered_worktree"):
            if not path.exists():
                act.update(action="prune", repo=f.get("registered_by"))
            else:
                st = git_work_status(path, head_only=True)
                if st["has_work"]:
                    act.update(action="refuse", reason="worktree has uncommitted, unpushed or stashed work", status=st)
                else:
                    act.update(action="worktree_remove", repo=f.get("registered_by"))
        elif kind == "cache_folder":
            act.update(action="remove")
        elif kind == "stray_file":
            act.update(action="move", target=str(_unique_target(cache_subdir("scratch", cache_dir), path.name)))
        else:
            repos = [path] if (path / ".git").is_dir() else nested_git_repos(path)
            busy = [git_work_status(r) for r in repos]
            busy = [b for b in busy if b["has_work"]]
            if busy:
                act.update(action="refuse", reason="contains a git repo with uncommitted, unpushed or stashed work", status=busy)
            else:
                sub = "deps" if kind == "duplicate_clone" or f["name"].lstrip("._").lower() in ("deps", "dep") else "scratch"
                act.update(action="move", target=str(_unique_target(cache_subdir(sub, cache_dir), path.name.lstrip(".") or path.name)))
        if act.get("target") and is_inside(Path(act["target"]), dev_root):
            act.update(action="refuse", reason=f"cache dir {cache_dir} is inside the dev root")
        actions.append(act)
    return actions


def _remove_tree(path: Path) -> None:
    def _onerror(func, p, _exc):  # read-only git objects on Windows
        os.chmod(p, 0o700)
        func(p)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_onerror)
    else:  # pragma: no cover
        shutil.rmtree(path, onerror=_onerror)


def apply_clean(actions: list[dict]) -> None:
    for act in actions:
        path = Path(act["path"])
        try:
            if act["action"] == "move":
                target = Path(act["target"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(target))
                act["done"] = True
            elif act["action"] == "remove":
                _remove_tree(path) if path.is_dir() else path.unlink()
                act["done"] = True
            elif act["action"] in ("worktree_remove", "prune"):
                repo = act.get("repo")
                if not repo:
                    code, common = _git(["-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"])
                    repo = str(Path(common).parent) if code == 0 and common else None
                if not repo:
                    act.update(done=False, error="could not find the main checkout for this worktree")
                    continue
                if act["action"] == "worktree_remove":
                    code, out = _git(["-C", repo, "worktree", "remove", str(path)])
                    if code != 0:
                        act.update(done=False, error=out or "git worktree remove failed")
                        continue
                _git(["-C", repo, "worktree", "prune"])
                act["done"] = True
            else:
                act["done"] = False
        except OSError as exc:
            act.update(done=False, error=str(exc))


# ---------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev-root", type=Path, default=None, help="dev root (default: ACS_DEV_ROOT or the OS default)")
    parser.add_argument("--cache-dir", type=Path, default=None, help="cache root (default: ACS_CACHE_DIR or the OS default)")
    parser.add_argument("--allow", action="append", default=[], help="top-level name to ignore (repeatable)")
    parser.add_argument("--clean", action="store_true", help="plan a cleanup (dry run unless --yes)")
    parser.add_argument("--yes", action="store_true", help="with --clean: actually move/remove")
    args = parser.parse_args(argv)

    dev_root = (args.dev_root or default_dev_root()).expanduser()
    if args.cache_dir:
        os.environ["ACS_CACHE_DIR"] = str(args.cache_dir)
    cache_dir = default_cache_dir()
    if not dev_root.is_dir():
        print(json.dumps({"dev_root": str(dev_root), "ok": False, "error": "dev root does not exist"}, indent=2))
        return 2
    if is_inside(cache_dir, dev_root):
        print(json.dumps({"dev_root": str(dev_root), "cache_dir": str(cache_dir), "ok": False,
                          "error": "cache dir is inside the dev root"}, indent=2))
        return 2

    report = scan(dev_root, allow=set(args.allow))
    if args.clean:
        actions = plan_clean(report, cache_dir)
        if args.yes:
            apply_clean(actions)
        report["clean"] = {"mode": "apply" if args.yes else "dry-run", "actions": actions}
        if args.yes:
            after = scan(dev_root, allow=set(args.allow))
            report["after"] = {"ok": after["ok"], "findings": after["findings"]}
            print(json.dumps(report, indent=2))
            return 0 if after["ok"] else 1
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
