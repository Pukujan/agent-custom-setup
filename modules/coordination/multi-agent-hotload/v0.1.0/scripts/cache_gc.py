#!/usr/bin/env python3
"""Remove finished scratch folders and linked worktrees from the ACS cache.

Agents put throwaway work under the ACS cache (see ``dev_root_check.py`` for
where that is): ``<cache>/scratch/<name>`` for probes and copies, and
``<cache>/worktrees/<repo>-<branch>`` for ``git worktree add``. Nothing removed
them, so the cache grew by gigabytes a day. This script is the cleanup.

Two commands:

* ``finish PATH...`` -- run when a task ends or its pull request merges. Removes
  that task's worktree (``git worktree remove``) and scratch folder right away,
  whatever their age. Use ``--dry-run`` to preview.
* ``gc`` -- lists every top-level entry of ``scratch/`` and ``worktrees/`` that
  has been idle for ``--days`` days (default 7) and removes them only with
  ``--yes``. Without ``--yes`` it is a dry run.

Both commands print what they kept and why. An entry is always kept when:

* a running process has its working directory inside it (``lsof -d cwd``; when
  ``lsof`` is unavailable nothing is removed). That includes the shell you run
  this from, so run it from outside the folder you are removing;
* any git checkout in it has uncommitted or untracked changes;
* any git checkout in it has commits that are not on a remote, unless GitHub
  reports a merged pull request whose head is exactly that commit (a squash
  merge whose branch was deleted);
* a full clone in it has stashes (a linked worktree's stashes live in the main
  repository and survive the removal, so they do not block);
* the worktree is locked (``git worktree lock``) or the entry holds an
  ``.acs-keep`` file;
* git cannot read it (for example its main repository is gone);
* (``gc`` only) anything in it changed within ``--days`` days.

Each entry is checked again immediately before it is removed. Paths outside
``<cache>/scratch`` and ``<cache>/worktrees`` are never touched; ``deps/`` is
left alone. Exit status: 0 when every planned removal succeeded (or on a dry
run), 1 when a removal failed, 2 on a usage error.

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
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_dev_root_check():
    spec = spec_from_file_location("dev_root_check", Path(__file__).with_name("dev_root_check.py"))
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


drc = _load_dev_root_check()

GC_KINDS = ("scratch", "worktrees")
KEEP_MARKER = ".acs-keep"
# Folders whose timestamps say nothing about whether a person is still working.
# ``.git`` is skipped too: git itself touches it (index refresh, fetch), and a
# commit made there is caught by the unpushed-commit check instead.
AGE_SKIP_DIRS = set(drc.CACHE_DIR_NAMES) | {".git"}
DAY = 86400.0


# ---------------------------------------------------------------- probes


def process_cwds() -> list[tuple[int, str, str]] | None:
    """(pid, command, cwd) for every process lsof can see, or None if it cannot run."""
    try:
        proc = subprocess.run(
            ["lsof", "-w", "-n", "-P", "-d", "cwd", "-F", "pcn"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None
    rows: list[tuple[int, str, str]] = []
    pid, cmd = 0, ""
    for line in proc.stdout.splitlines():
        tag, value = line[:1], line[1:]
        if tag == "p":
            pid, cmd = int(value or 0), ""
        elif tag == "c":
            cmd = value
        elif tag == "n" and value.startswith("/") and pid != os.getpid() and cmd != "lsof":
            rows.append((pid, cmd, drc._norm(Path(value))))
    if proc.returncode != 0 and not rows:
        return None
    return rows


def processes_inside(path: Path, cwds: list[tuple[int, str, str]]) -> list[str]:
    root = drc._norm(path).rstrip("\\/")
    return [f"{cmd or '?'} (pid {pid})" for pid, cmd, cwd in cwds if cwd == root or cwd.startswith(root + os.sep)]


def tree_stats(path: Path) -> tuple[int, float]:
    """(size in bytes, newest mtime) for a file or folder, without following symlinks.

    Tool caches and ``.git`` count toward the size but not the age: ``npm
    install`` or ``git fetch`` there is not a sign someone is still working.
    """
    try:
        st = path.lstat()
    except OSError:
        return 0, 0.0
    if not path.is_dir() or path.is_symlink():
        return st.st_size, st.st_mtime
    size, newest = 0, st.st_mtime
    stack: list[tuple[str, bool]] = [(str(path), True)]
    while stack:
        cur, counts = stack.pop()
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        est = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    size += est.st_size
                    is_dir = entry.is_dir(follow_symlinks=False)
                    entry_counts = counts and not (is_dir and entry.name in AGE_SKIP_DIRS)
                    if entry_counts and est.st_mtime > newest:
                        newest = est.st_mtime
                    if is_dir:
                        stack.append((entry.path, entry_counts))
        except OSError:
            continue
    return size, newest


def _git(args: list[str], cwd: Path) -> tuple[int, str]:
    # --no-optional-locks: a read-only scan must not rewrite the index.
    return drc._git(["-C", str(cwd), "--no-optional-locks", *args])


def merged_pr_at(path: Path, head: str) -> str | None:
    """URL of a merged GitHub PR whose head commit is ``head``, else None."""
    code, branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], path)
    if code != 0 or not branch or branch == "HEAD":
        return None
    try:
        proc = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--state", "merged", "--json", "url,headRefOid", "--limit", "20"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        prs = json.loads(proc.stdout) if proc.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return next((pr.get("url") for pr in prs if pr.get("headRefOid") == head), None)


def git_blockers(repo: Path, *, linked: bool, use_gh: bool, label: str | None = None) -> list[str]:
    """Reasons this checkout must be kept; empty when removing it loses nothing."""
    name = label or str(repo)
    code, out = _git(["status", "--porcelain"], repo)
    if code != 0:
        return [f"git cannot read {name} (main repository missing?); check it by hand"]
    dirty = [ln for ln in out.splitlines() if ln.strip()]
    reasons = []
    if dirty:
        reasons.append(f"{len(dirty)} uncommitted or untracked change(s) in {name}")
    revs = ["HEAD"] if linked else ["HEAD", "--branches"]
    code, out = _git(["log", "--format=%H", *revs, "--not", "--remotes"], repo)
    if code != 0 and not linked:  # empty repo: no HEAD yet
        code, out = _git(["log", "--format=%H", "--branches", "--not", "--remotes"], repo)
    unpushed = [ln for ln in out.splitlines() if ln.strip()] if code == 0 else []
    if unpushed:
        _, head = _git(["rev-parse", "HEAD"], repo)
        # Only a linked worktree's HEAD is checked against GitHub: a full clone can
        # hold other unpushed branches that no single PR accounts for.
        pr = merged_pr_at(repo, head) if (linked and use_gh and head) else None
        if not pr:
            reasons.append(f"{len(unpushed)} commit(s) not on any remote in {name}")
    if not linked:
        code, out = _git(["stash", "list"], repo)
        stashes = [ln for ln in out.splitlines() if ln.strip()] if code == 0 else []
        if stashes:
            reasons.append(f"{len(stashes)} stash(es) in {name}")
    return reasons


def worktree_lock(path: Path) -> str | None:
    """The lock reason of a linked worktree, '' when locked without one, None when unlocked."""
    code, gitdir = _git(["rev-parse", "--absolute-git-dir"], path)
    if code != 0 or not gitdir:
        return None
    lock = Path(gitdir) / "locked"
    if not lock.exists():
        return None
    try:
        return lock.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def main_repo_of(path: Path) -> Path | None:
    code, common = _git(["rev-parse", "--path-format=absolute", "--git-common-dir"], path)
    if code != 0 or not common:
        return None
    common_path = Path(common)
    return common_path.parent if common_path.name == ".git" else common_path


# ---------------------------------------------------------------- assess


def cache_kind(path: Path, cache_dir: Path) -> str | None:
    """'scratch' or 'worktrees' when ``path`` is a top-level entry there, else None."""
    parent = drc._norm(path.parent)
    for kind in GC_KINDS:
        if parent == drc._norm(cache_dir / kind):
            return kind
    return None


def assess(
    path: Path,
    *,
    cache_dir: Path,
    cwds: list[tuple[int, str, str]] | None,
    min_idle_days: float | None,
    now: float | None = None,
    use_gh: bool = True,
) -> dict:
    """Decide whether one cache entry can go. Read-only."""
    now = time.time() if now is None else now
    kind = cache_kind(path, cache_dir)
    item: dict = {"path": str(path), "kind": kind, "action": "keep", "reasons": []}
    reasons: list[str] = item["reasons"]
    if kind is None:
        reasons.append(f"not a top-level entry of {cache_dir / 'scratch'} or {cache_dir / 'worktrees'}")
        return item
    if not path.exists() and not path.is_symlink():
        reasons.append("does not exist")
        return item

    size, newest = tree_stats(path)
    item["size_bytes"] = size
    item["idle_days"] = round(max(0.0, now - newest) / DAY, 1)

    if path.is_symlink():
        item["type"] = "symlink"
        if min_idle_days is not None and item["idle_days"] < min_idle_days:
            reasons.append(f"changed {item['idle_days']}d ago (< {min_idle_days:g}d)")
        if not reasons:
            item["action"] = "remove"
        return item

    is_dir = path.is_dir()
    if min_idle_days is not None and item["idle_days"] < min_idle_days:
        reasons.append(f"changed {item['idle_days']}d ago (< {min_idle_days:g}d)")

    if is_dir:
        if cwds is None:
            reasons.append("cannot check for running processes (lsof unavailable)")
        else:
            busy = processes_inside(path, cwds)
            if busy:
                reasons.append("process running inside: " + ", ".join(busy[:3]) + (" ..." if len(busy) > 3 else ""))
        if (path / KEEP_MARKER).exists():
            reasons.append(f"{KEEP_MARKER} marker present")

    git_marker = path / ".git"
    if is_dir and git_marker.is_file():
        item["type"] = "linked_worktree"
        lock = worktree_lock(path)
        if lock is not None:
            reasons.append("worktree is locked" + (f": {lock}" if lock else ""))
        reasons.extend(git_blockers(path, linked=True, use_gh=use_gh, label=path.name))
        repo = main_repo_of(path)
        if repo is None and not any(r.startswith("git cannot read") for r in reasons):
            reasons.append("cannot find the main repository of this worktree")
        item["repo"] = str(repo) if repo else None
        action = "worktree_remove"
    elif is_dir:
        item["type"] = "git_clone" if git_marker.is_dir() else "folder"
        for repo in drc.nested_git_repos(path, max_depth=8):
            rel = repo.relative_to(path).as_posix()
            label = path.name if rel == "." else f"{path.name}/{rel}"
            reasons.extend(git_blockers(repo, linked=(repo / ".git").is_file(), use_gh=use_gh, label=label))
        action = "remove"
    else:
        item["type"] = "file"
        action = "remove"

    if not reasons:
        item["action"] = action
    return item


# ---------------------------------------------------------------- act


def remove(item: dict) -> None:
    path = Path(item["path"])
    try:
        if item["action"] == "worktree_remove":
            repo = item.get("repo")
            code, out = drc._git(["-C", repo, "worktree", "remove", str(path)])
            if code != 0:
                item.update(done=False, error=out or "git worktree remove failed")
                return
            drc._git(["-C", repo, "worktree", "prune"])
        elif path.is_symlink() or not path.is_dir():
            path.unlink()
        else:
            drc._remove_tree(path)
        item["done"] = True
    except OSError as exc:
        item.update(done=False, error=str(exc))


def run(paths: list[Path], *, cache_dir: Path, min_idle_days: float | None, apply: bool, use_gh: bool = True) -> list[dict]:
    """Assess ``paths`` and, when ``apply``, remove the safe ones after a fresh re-check."""
    cwds = process_cwds()
    items = [assess(p, cache_dir=cache_dir, cwds=cwds, min_idle_days=min_idle_days, use_gh=use_gh) for p in paths]
    if not apply:
        return items
    for i, item in enumerate(items):
        if item["action"] == "keep":
            continue
        # Re-check right before acting: a session may have started since the scan.
        fresh = assess(Path(item["path"]), cache_dir=cache_dir, cwds=process_cwds(),
                       min_idle_days=min_idle_days, use_gh=use_gh)
        if fresh["action"] == "keep":
            fresh["reasons"].insert(0, "changed since the scan")
            items[i] = fresh
            continue
        remove(fresh)
        items[i] = fresh
    return items


def gc_candidates(cache_dir: Path) -> list[Path]:
    out: list[Path] = []
    for kind in GC_KINDS:
        base = cache_dir / kind
        if base.is_dir():
            out.extend(sorted((p for p in base.iterdir() if p.name not in drc.IGNORED_NAMES), key=lambda p: p.name.lower()))
    return out


# ---------------------------------------------------------------- output


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def render(items: list[dict], *, cache_dir: Path, apply: bool, header: str) -> str:
    lines = [header, ""]
    order = {"remove": 0, "worktree_remove": 0, "keep": 1}
    freed = 0
    for item in sorted(items, key=lambda i: (order.get(i["action"], 2), -i.get("size_bytes", 0))):
        try:
            rel = str(Path(item["path"]).relative_to(cache_dir))
        except ValueError:
            rel = item["path"]
        size = human_size(item.get("size_bytes", 0)).rjust(8)
        if item["action"] == "keep":
            lines.append(f"KEEP     {size}  {rel}  -- " + "; ".join(item["reasons"]))
            continue
        how = "git worktree remove" if item["action"] == "worktree_remove" else "delete"
        if not apply:
            label = "REMOVE"
        elif item.get("done"):
            label, freed = "REMOVED", freed + item.get("size_bytes", 0)
        else:
            label = "FAILED"
        note = f"idle {item.get('idle_days', 0)}d, nothing unsaved ({how})"
        if item.get("error"):
            note += f" -- {item['error']}"
        lines.append(f"{label:<8} {size}  {rel}  -- {note}")
    removable = [i for i in items if i["action"] != "keep"]
    total = sum(i.get("size_bytes", 0) for i in removable)
    lines.append("")
    if apply:
        lines.append(f"Freed {human_size(freed)}; kept {len(items) - len(removable)} entr{'y' if len(items) - len(removable) == 1 else 'ies'}.")
    else:
        lines.append(f"Dry run: {len(removable)} entr{'y' if len(removable) == 1 else 'ies'} ({human_size(total)}) can go; "
                     f"kept {len(items) - len(removable)}. Nothing was changed.")
    return "\n".join(lines)


# ---------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache-dir", type=Path, default=None, help="cache root (default: ACS_CACHE_DIR or the OS default)")
    parser.add_argument("--json", action="store_true", help="print a JSON report instead of text")
    parser.add_argument("--no-gh", action="store_true", help="do not ask GitHub whether unpushed commits were merged")
    sub = parser.add_subparsers(dest="command", required=True)
    gc = sub.add_parser("gc", help="list idle scratch folders and worktrees; remove them with --yes")
    gc.add_argument("--days", type=float, default=7.0, help="idle for at least this many days (default 7)")
    gc.add_argument("--yes", action="store_true", help="actually remove (default: dry run)")
    fin = sub.add_parser("finish", help="remove a finished task's worktree and scratch folder now")
    fin.add_argument("paths", nargs="+", type=Path, help="worktree or scratch folder (top-level entry of the cache)")
    fin.add_argument("--dry-run", action="store_true", help="only report what would happen")
    args = parser.parse_args(argv)

    if args.cache_dir:
        os.environ["ACS_CACHE_DIR"] = str(args.cache_dir)
    cache_dir = drc.default_cache_dir().expanduser()

    if args.command == "gc":
        apply, min_idle = args.yes, args.days
        paths = gc_candidates(cache_dir)
        header = (f"acs cache gc: {cache_dir} -- entries idle >= {args.days:g} days "
                  + ("(removing)" if apply else "(dry run; add --yes to remove)"))
    else:
        apply, min_idle = not args.dry_run, None
        paths = [p.expanduser().absolute() for p in args.paths]
        header = f"acs cache finish: {cache_dir} " + ("(removing)" if apply else "(dry run)")

    items = run(paths, cache_dir=cache_dir, min_idle_days=min_idle, apply=apply, use_gh=not args.no_gh)
    if args.json:
        print(json.dumps({"cache_dir": str(cache_dir), "command": args.command,
                          "mode": "apply" if apply else "dry-run", "items": items}, indent=2))
    else:
        print(render(items, cache_dir=cache_dir, apply=apply, header=header))
    failed = [i for i in items if i["action"] != "keep" and apply and not i.get("done")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
