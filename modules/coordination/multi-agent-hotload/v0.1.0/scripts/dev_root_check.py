#!/usr/bin/env python3
"""Check the dev root layout: one project folder (or legacy flat checkout) per repo.

The dev root (``D:\\development`` on Windows, ``~/development`` elsewhere;
override with ``ACS_DEV_ROOT`` or ``--dev-root``) holds exactly one entry per
repo, in one of two shapes:

* **Project folder (preferred)** -- ``<dev>/<project>/`` is not a git repo. It
  holds ``main/`` (the primary checkout, ``.git`` is a directory) and, when the
  repo needs parallel work, ``worktrees/<task>/`` (linked worktrees of that
  ``main``)::

      D:\\development\\octo-db\\main\\
      D:\\development\\octo-db\\worktrees\\OCTO-0114\\

* **Legacy flat checkout** -- ``<dev>/<repo>`` is itself the primary checkout.
  Still accepted; ``--migrate <repo>`` plans the move to the project layout.

Worktrees never sit directly in the dev root and never nest inside a main
checkout. Dependency clones, scratch work and caches never live in the dev root
at all; they belong in the per-user ACS cache:

* Windows: ``%LOCALAPPDATA%\\acs\\{deps,scratch}``
* macOS / Linux: ``$XDG_CACHE_HOME/acs/...`` (default ``~/.cache/acs/...``)

Override the cache root with ``ACS_CACHE_DIR``.

Findings (``kind``):

* ``not_git``              -- a plain directory that is neither a checkout nor a project folder
* ``dot_or_dep_folder``    -- a dot- or underscore-folder such as ``.scratch`` or ``_deps``
* ``stray_file``           -- a loose file at the top level
* ``cache_folder``         -- a tool cache (``node_modules``, ``.venv``...) at the top level
* ``linked_worktree``      -- a linked worktree (``.git`` is a file) directly in the dev root
* ``duplicate_clone``      -- a second checkout of a remote that already has an entry
* ``registered_worktree``  -- a worktree registered inside the dev root in the wrong place
  (nested in a checkout, or outside ``<project>/worktrees/``)
* ``project_extra_entry``  -- something other than ``main/`` and ``worktrees/`` in a project folder
* ``project_main_not_primary`` -- a project folder whose ``main/`` is a linked worktree
* ``worktrees_entry_not_worktree`` -- a clone, folder or file under ``<project>/worktrees/``
* ``foreign_worktree``     -- a worktree under ``<project>/worktrees/`` that belongs to another repo

It prints a JSON report and exits 1 when it finds anything, 0 when the root is
clean, and 2 on a usage problem (missing dev root, cache inside the dev root).

``--clean`` plans a fix for each finding; it is a dry run unless ``--yes`` is
also given. It never touches a git repo (or a folder containing one) that has
uncommitted changes, commits not on any remote, or stashes, and it never moves
a project's ``main/`` or its valid worktrees. Misplaced worktrees of a project
are moved into ``<project>/worktrees/`` with ``git worktree move``; other safe
linked worktrees are removed with ``git worktree remove`` + ``prune``; other
safe entries are moved into the cache; top-level tool caches are removed.

``--migrate <repo>`` plans moving the flat checkout ``<dev>/<repo>`` to
``<dev>/<repo>/main`` and every linked worktree of it to
``<dev>/<repo>/worktrees/<name>`` (then ``git worktree repair`` + ``prune``).
It refuses when the checkout or any worktree has uncommitted, unpushed or
stashed work, or a worktree is locked, and does nothing without ``--yes``.

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
CACHE_SUBDIRS = ("deps", "scratch", "worktrees")  # worktrees/ kept for older callers


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
    """True for a main checkout the dev root may hold.

    That is ``<dev>/<repo>`` (legacy flat checkout) or ``<dev>/<project>/main``
    (project folder), with ``.git`` a directory in both cases.
    """
    if not (path / ".git").is_dir():
        return False
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        return False
    root = _norm(dev_root)
    if _norm(resolved.parent) == root:
        return True
    return (
        resolved.name == "main"
        and _norm(resolved.parent.parent) == root
        and not (resolved.parent / ".git").exists()
    )


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
    u = url.strip().lower().replace("\\", "/").rstrip("/")
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


def worktree_entries(repo: Path) -> list[dict]:
    """``git worktree list --porcelain`` as dicts (path, branch, locked, prunable)."""
    code, out = _git(["-C", str(repo), "worktree", "list", "--porcelain"])
    if code != 0:
        return []
    entries: list[dict] = []
    cur: dict | None = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            cur = {"path": Path(line[len("worktree "):]), "locked": False}
            entries.append(cur)
        elif cur is not None and line.startswith("branch "):
            cur["branch"] = line[len("branch "):]
        elif cur is not None and (line == "locked" or line.startswith("locked ")):
            cur["locked"] = True
        elif cur is not None and (line == "prunable" or line.startswith("prunable ")):
            cur["prunable"] = True
    return entries


def git_common_dir(path: Path) -> Path | None:
    """The shared ``.git`` directory of the checkout or worktree at ``path``."""
    code, out = _git(["-C", str(path), "rev-parse", "--path-format=absolute", "--git-common-dir"])
    if code != 0 or not out:
        return None
    return Path(out)


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


def _is_project_folder(entry: Path) -> bool:
    return (
        entry.is_dir()
        and not (entry / ".git").exists()
        and (entry / "main").is_dir()
        and (entry / "main" / ".git").exists()
    )


def _scan_project(entry: Path, findings: list[dict]) -> Path | None:
    """Check one project folder; return its main checkout if it is a usable primary."""
    main = entry / "main"
    if not (main / ".git").is_dir():
        findings.append(
            _finding(
                entry,
                "project_main_not_primary",
                "main/ is a linked worktree, not a primary checkout",
                project=entry.name,
            )
        )
        return None
    for child in sorted(entry.iterdir(), key=lambda p: p.name.lower()):
        if child.name in ("main", "worktrees") or child.name in IGNORED_NAMES:
            continue
        findings.append(
            _finding(
                child,
                "project_extra_entry",
                "only main/ and worktrees/ belong in a project folder",
                project=entry.name,
            )
        )
    wt_dir = entry / "worktrees"
    if wt_dir.exists() and not wt_dir.is_dir():
        findings.append(
            _finding(wt_dir, "project_extra_entry", "worktrees must be a folder", project=entry.name)
        )
    elif wt_dir.is_dir():
        main_common = git_common_dir(main)
        for child in sorted(wt_dir.iterdir(), key=lambda p: p.name.lower()):
            if child.name in IGNORED_NAMES:
                continue
            marker = child / ".git"
            if not child.is_dir() or not marker.exists():
                findings.append(
                    _finding(
                        child,
                        "worktrees_entry_not_worktree",
                        "not a git worktree; worktrees/ holds only linked worktrees of main/",
                        project=entry.name,
                    )
                )
            elif marker.is_dir():
                findings.append(
                    _finding(
                        child,
                        "worktrees_entry_not_worktree",
                        "a full clone, not a linked worktree of main/",
                        project=entry.name,
                    )
                )
            else:
                common = git_common_dir(child)
                if common is None or main_common is None or _norm(common) != _norm(main_common):
                    findings.append(
                        _finding(
                            child,
                            "foreign_worktree",
                            f"linked worktree of another repo ({common}), not of {main}",
                            project=entry.name,
                        )
                    )
    return main


def scan(dev_root: Path, *, allow: set[str] | None = None) -> dict:
    """Return the report dict for ``dev_root`` (does not change anything)."""
    allow = {a.lower() for a in (allow or set())}
    dev_root = dev_root.expanduser()
    findings: list[dict] = []
    # remote key -> list of (top-level entry, main checkout path, layout)
    repos: dict[str, list[tuple[Path, Path, str]]] = {}

    for entry in sorted(dev_root.iterdir(), key=lambda p: p.name.lower()):
        name = entry.name
        if name in IGNORED_NAMES or name.lower() in allow:
            continue
        if not entry.is_dir():
            findings.append(_finding(entry, "stray_file", "loose file at the top of the dev root"))
            continue
        if name.startswith((".", "_")):
            kind = "cache_folder" if name in CACHE_DIR_NAMES else "dot_or_dep_folder"
            findings.append(_finding(entry, kind, "dot/underscore folder (scratch, deps or cache)"))
            continue
        git_marker = entry / ".git"
        if git_marker.is_file():
            findings.append(
                _finding(
                    entry,
                    "linked_worktree",
                    ".git is a file: a linked worktree directly in the dev root; "
                    "worktrees belong at <project>/worktrees/<task>",
                )
            )
            continue
        if git_marker.is_dir():
            main, layout = entry, "flat"
        elif _is_project_folder(entry):
            main = _scan_project(entry, findings)
            layout = "project"
            if main is None:
                continue
        elif name in CACHE_DIR_NAMES:
            findings.append(_finding(entry, "cache_folder", "tool cache at the top of the dev root"))
            continue
        else:
            findings.append(_finding(entry, "not_git", "plain folder: not a checkout and not a project folder with main/"))
            continue
        remote = git_remote(main)
        key = normalize_remote(remote) if remote else f"<no-remote>:{_norm(main)}"
        repos.setdefault(key, []).append((entry, main, layout))

    # Duplicate clones: keep the entry named after the remote, then a project folder, then the first.
    kept: list[tuple[Path, Path, str]] = []
    for key, items in repos.items():
        if len(items) == 1:
            kept.append(items[0])
            continue
        repo_name = key.rsplit("/", 1)[-1]
        keep = (
            next((it for it in items if it[0].name.lower() == repo_name), None)
            or next((it for it in items if it[2] == "project"), None)
            or items[0]
        )
        kept.append(keep)
        for it in items:
            if it is keep:
                continue
            findings.append(
                _finding(
                    it[0],
                    "duplicate_clone",
                    f"second checkout of {key}; primary is {keep[0].name}",
                    remote=key,
                    primary=str(keep[0]),
                )
            )

    # Worktrees registered by kept main checkouts that live in the wrong place in the dev root.
    by_path = {_norm(Path(f["path"])): f for f in findings}
    for entry, main, layout in kept:
        allowed_dir = entry / "worktrees" if layout == "project" else None
        for wt in registered_worktrees(main):
            if not is_inside(wt, dev_root):
                continue
            if allowed_dir is not None and is_inside(wt, allowed_dir) and _norm(wt.parent) == _norm(allowed_dir):
                continue
            n = _norm(wt)
            extra = {"registered_by": str(main), "layout": layout}
            if allowed_dir is not None:
                extra["target"] = str(allowed_dir / wt.name)
            if n in by_path:
                by_path[n].update(extra)
                continue
            exists = wt.exists()
            where = (
                "outside <project>/worktrees/"
                if layout == "project"
                else "inside the dev root for a flat checkout (migrate it, or move the worktree out)"
            )
            f = _finding(
                wt,
                "registered_worktree",
                f"worktree registered {where}" + ("" if exists else " (path missing; prunable)"),
                exists=exists,
                **extra,
            )
            findings.append(f)
            by_path[n] = f

    flat = sorted(e.name for e, _m, layout in kept if layout == "flat")
    projects = sorted(e.name for e, _m, layout in kept if layout == "project")
    return {
        "dev_root": str(dev_root),
        "cache_dir": str(default_cache_dir()),
        "ok": not findings,
        "primary_checkouts": sorted(e.name for e, _m, _l in kept),
        "project_folders": projects,
        "flat_checkouts": flat,
        "findings": findings,
    }


# ---------------------------------------------------------------- clean


def _unique_target(base: Path, name: str) -> Path:
    target = base / name
    if not target.exists():
        return target
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return base / f"{name}-{stamp}"


def _work_refusal(paths: list[Path], *, head_only: bool = False) -> dict | None:
    busy = [st for st in (git_work_status(p, head_only=head_only) for p in paths) if st["has_work"]]
    if busy:
        return {"action": "refuse", "reason": "has uncommitted, unpushed or stashed work", "status": busy}
    return None


def plan_clean(report: dict, cache_dir: Path) -> list[dict]:
    """Decide what to do with each finding. Pure apart from read-only git calls."""
    dev_root = Path(report["dev_root"])
    actions: list[dict] = []
    for f in report["findings"]:
        path = Path(f["path"])
        kind = f["kind"]
        act: dict = {"path": str(path), "kind": kind}
        is_worktree = kind in ("linked_worktree", "registered_worktree", "foreign_worktree")
        if is_worktree and not path.exists():
            act.update(action="prune", repo=f.get("registered_by"))
        elif is_worktree and f.get("target") and kind != "foreign_worktree":
            # A project's own worktree in the wrong place: move it home (git keeps the work).
            target = Path(f["target"])
            if target.exists():
                act.update(action="refuse", reason=f"{target} already exists")
            else:
                act.update(action="worktree_move", repo=f.get("registered_by"), target=str(target))
        elif is_worktree:
            refusal = _work_refusal([path], head_only=True)
            if refusal:
                act.update(refusal)
            else:
                act.update(action="worktree_remove", repo=f.get("registered_by"))
        elif kind == "cache_folder":
            act.update(action="remove")
        elif kind == "stray_file" or (kind in ("project_extra_entry", "worktrees_entry_not_worktree") and not path.is_dir()):
            act.update(action="move", target=str(_unique_target(cache_subdir("scratch", cache_dir), path.name)))
        elif kind == "project_main_not_primary":
            act.update(action="refuse", reason="main/ must be a primary checkout; fix this by hand")
        else:
            repos = [path] if (path / ".git").exists() else nested_git_repos(path)
            refusal = _work_refusal(repos)
            if refusal:
                act.update(refusal)
                act["reason"] = "contains a git repo with uncommitted, unpushed or stashed work"
            else:
                sub = "deps" if kind == "duplicate_clone" or f["name"].lstrip("._").lower() in ("deps", "dep") else "scratch"
                act.update(action="move", target=str(_unique_target(cache_subdir(sub, cache_dir), path.name.lstrip(".") or path.name)))
        if act.get("action") == "move" and is_inside(Path(act["target"]), dev_root):
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
            elif act["action"] == "worktree_move":
                target = Path(act["target"])
                target.parent.mkdir(parents=True, exist_ok=True)
                code, out = _git(["-C", act["repo"], "worktree", "move", str(path), str(target)])
                act.update(done=code == 0)
                if code != 0:
                    act["error"] = out or "git worktree move failed"
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


# ---------------------------------------------------------------- migrate


def plan_migrate(dev_root: Path, repo_name: str) -> dict:
    """Plan moving flat ``<dev>/<repo>`` to ``<dev>/<repo>/main`` + ``worktrees/``."""
    flat = dev_root / repo_name
    plan: dict = {"repo": repo_name, "from": str(flat), "steps": [], "ok": False}
    if not (flat / ".git").is_dir():
        plan["error"] = f"{flat} is not a flat primary checkout (.git must be a directory)"
        return plan
    if _norm(flat.parent) != _norm(dev_root):
        plan["error"] = f"{flat} is not directly in the dev root"
        return plan
    main = flat / "main"
    if main.exists():
        plan["error"] = f"{main} already exists inside the checkout; resolve that first"
        return plan
    entries = [e for e in worktree_entries(flat) if _norm(e["path"]) != _norm(flat)]
    problems: list[dict] = []
    st = git_work_status(flat)
    # A worktree nested in the checkout shows up as untracked there; that is not work to lose.
    nested_wts = [e["path"] for e in entries if is_inside(e["path"], flat)]

    def _is_nested_wt_line(line: str) -> bool:
        if not line.startswith("?? "):
            return False
        untracked = flat / line[3:].strip().strip('"').rstrip("/")
        return any(is_inside(wt, untracked) for wt in nested_wts)

    st["dirty"] = [ln for ln in st["dirty"] if not _is_nested_wt_line(ln)]
    st["has_work"] = bool(st["dirty"] or st["unpushed"] or st["stashes"])
    if st["has_work"]:
        problems.append(st)
    worktrees: list[dict] = []
    used: set[str] = set()
    for e in entries:
        wt = e["path"]
        if e.get("prunable") or not wt.exists():
            plan["steps"].append({"action": "prune", "path": str(wt)})
            continue
        if e.get("locked"):
            problems.append({"path": str(wt), "locked": True})
            continue
        wst = git_work_status(wt, head_only=True)
        if wst["has_work"]:
            problems.append(wst)
        name = wt.name
        while name.lower() in used or name.lower() == "main":
            name = f"{name}-wt"
        used.add(name.lower())
        nested = is_inside(wt, flat)
        after_main_move = main / wt.relative_to(flat) if nested else wt
        worktrees.append({"from": str(wt), "via": str(after_main_move), "to": str(flat / "worktrees" / name)})
    if problems:
        plan["error"] = "refusing: uncommitted, unpushed or stashed work, or a locked worktree"
        plan["problems"] = problems
        return plan
    tmp = dev_root / f"{repo_name}.acs-migrate"
    if tmp.exists():
        plan["error"] = f"{tmp} already exists"
        return plan
    plan["steps"][:0] = [
        {"action": "rename", "from": str(flat), "to": str(tmp)},
        {"action": "mkdir", "path": str(flat)},
        {"action": "rename", "from": str(tmp), "to": str(main)},
        {"action": "worktree_repair", "repo": str(main), "paths": [w["via"] for w in worktrees]},
    ]
    for w in worktrees:
        plan["steps"].append({"action": "worktree_move", "repo": str(main), "from": w["via"], "to": w["to"]})
    plan["steps"].append({"action": "worktree_prune", "repo": str(main)})
    plan["ok"] = True
    return plan


def apply_migrate(plan: dict) -> None:
    """Run a plan from ``plan_migrate``. Stops at the first failed step."""
    for step in plan["steps"]:
        act = step["action"]
        try:
            if act == "rename":
                os.rename(step["from"], step["to"])
                code, out = 0, ""
            elif act == "mkdir":
                Path(step["path"]).mkdir()
                code, out = 0, ""
            elif act == "worktree_repair":
                code, out = _git(["-C", step["repo"], "worktree", "repair", *step["paths"]])
            elif act == "worktree_move":
                Path(step["to"]).parent.mkdir(parents=True, exist_ok=True)
                code, out = _git(["-C", step["repo"], "worktree", "move", step["from"], step["to"]])
            elif act in ("worktree_prune", "prune"):
                repo = step.get("repo") or plan["steps"][2]["to"]
                code, out = _git(["-C", repo, "worktree", "prune"])
            else:
                code, out = 1, f"unknown step {act}"
        except OSError as exc:
            code, out = 1, str(exc)
        step["done"] = code == 0
        if code != 0:
            step["error"] = out or "failed"
            plan["ok"] = False
            plan["error"] = f"stopped at step {act}; earlier steps already ran"
            return


# ---------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev-root", type=Path, default=None, help="dev root (default: ACS_DEV_ROOT or the OS default)")
    parser.add_argument("--cache-dir", type=Path, default=None, help="cache root (default: ACS_CACHE_DIR or the OS default)")
    parser.add_argument("--allow", action="append", default=[], help="top-level name to ignore (repeatable)")
    parser.add_argument("--clean", action="store_true", help="plan a cleanup (dry run unless --yes)")
    parser.add_argument("--yes", action="store_true", help="with --clean or --migrate: actually do it")
    parser.add_argument(
        "--migrate",
        metavar="REPO",
        default=None,
        help="plan moving flat <dev>/REPO into REPO/main + REPO/worktrees (dry run unless --yes)",
    )
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

    if args.migrate:
        plan = plan_migrate(dev_root, args.migrate)
        plan["mode"] = "apply" if args.yes and plan["ok"] else "dry-run"
        if args.yes and plan["ok"]:
            apply_migrate(plan)
        print(json.dumps(plan, indent=2))
        return 0 if plan["ok"] else 1

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
