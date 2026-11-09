"""Tests for cache_gc.py (finish / gc of the ACS cache).

Every test builds a fake ACS cache under tmp_path (ACS_CACHE_DIR), a bare
'origin' and a main checkout, so nothing on the real machine is read or
changed. The process probe and GitHub lookup are stubbed unless a test is
about them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = MODULE_ROOT / "scripts"

GIT_CFG = [
    "-c", "user.name=ACS Test",
    "-c", "user.email=acs-test@example.invalid",
    "-c", "commit.gpgsign=false",
    "-c", "init.defaultBranch=main",
    "-c", "core.autocrlf=false",
]


def _load():
    spec = spec_from_file_location("cache_gc", SCRIPTS / "cache_gc.py")
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(["git", *GIT_CFG, *args], cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stdout}{proc.stderr}"
    return proc.stdout.strip()


def age(path: Path, days: float) -> None:
    """Backdate every file and folder under ``path`` (and ``path``) by ``days``."""
    t = time.time() - days * 86400
    for dirpath, dirnames, filenames in os.walk(path):
        for name in [*dirnames, *filenames]:
            os.utime(os.path.join(dirpath, name), (t, t), follow_symlinks=False)
    os.utime(path, (t, t), follow_symlinks=False)


@pytest.fixture()
def gc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("ACS_CACHE_DIR", str(tmp_path / "cache"))
    mod = _load()
    monkeypatch.setattr(mod, "process_cwds", lambda: [])
    monkeypatch.setattr(mod, "merged_pr_at", lambda path, head: None)
    return mod


@pytest.fixture()
def cache(tmp_path: Path) -> Path:
    root = tmp_path / "cache"
    for kind in ("scratch", "worktrees", "deps"):
        (root / kind).mkdir(parents=True)
    return root


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A main checkout of a bare 'origin', with main pushed."""
    remote = tmp_path / "origin.git"
    git("init", "--bare", str(remote))
    main = tmp_path / "dev" / "widget"
    main.parent.mkdir()
    git("clone", str(remote), str(main))
    (main / "README.md").write_text("hi\n", encoding="utf-8")
    git("add", ".", cwd=main)
    git("commit", "-m", "init", cwd=main)
    git("push", "origin", "main", cwd=main)
    return main


def add_worktree(repo: Path, cache: Path, name: str, *, push: bool = True) -> Path:
    path = cache / "worktrees" / name
    git("worktree", "add", "-b", f"task/{name}", str(path), cwd=repo)
    (path / f"{name}.txt").write_text("work\n", encoding="utf-8")
    git("add", ".", cwd=path)
    git("commit", "-m", f"work on {name}", cwd=path)
    if push:
        git("push", "origin", f"task/{name}", cwd=path)
    return path


def scratch_dir(cache: Path, name: str) -> Path:
    path = cache / "scratch" / name
    (path / "sub").mkdir(parents=True)
    (path / "sub" / "probe.log").write_text("x\n", encoding="utf-8")
    return path


def by_name(items: list[dict]) -> dict[str, dict]:
    return {Path(i["path"]).name: i for i in items}


# ---------------------------------------------------------------- gc


def test_gc_dry_run_plans_but_changes_nothing(gc, cache: Path, repo: Path):
    wt = add_worktree(repo, cache, "done-task")
    folder = scratch_dir(cache, "old-probe")
    loose = cache / "scratch" / "shot.png"
    loose.write_bytes(b"png")
    for p in (wt, folder, loose):
        age(p, 10)

    items = by_name(gc.run(gc.gc_candidates(cache), cache_dir=cache, min_idle_days=7, apply=False))
    assert items["done-task"]["action"] == "worktree_remove"
    assert items["old-probe"]["action"] == "remove"
    assert items["shot.png"]["action"] == "remove"
    assert wt.exists() and folder.exists() and loose.exists()


def test_gc_yes_removes_idle_clean_entries(gc, cache: Path, repo: Path):
    wt = add_worktree(repo, cache, "done-task")
    folder = scratch_dir(cache, "old-probe")
    for p in (wt, folder):
        age(p, 10)

    items = by_name(gc.run(gc.gc_candidates(cache), cache_dir=cache, min_idle_days=7, apply=True))
    assert items["done-task"]["done"] and items["old-probe"]["done"]
    assert not wt.exists() and not folder.exists()
    assert str(wt) not in git("worktree", "list", cwd=repo)
    assert (cache / "deps").is_dir()  # deps/ is never a candidate


def test_gc_keeps_recent_entries(gc, cache: Path):
    folder = scratch_dir(cache, "fresh")
    age(folder, 10)
    (folder / "sub" / "probe.log").write_text("touched today\n", encoding="utf-8")
    item = gc.run([folder], cache_dir=cache, min_idle_days=7, apply=True)[0]
    assert item["action"] == "keep"
    assert "changed" in item["reasons"][0]
    assert folder.exists()


def test_git_internals_do_not_count_as_activity(gc, cache: Path, repo: Path):
    wt = add_worktree(repo, cache, "old-task")
    age(wt, 10)
    os.utime(repo / ".git" / "index")  # e.g. a fetch or index refresh in the shared repo
    item = gc.run([wt], cache_dir=cache, min_idle_days=7, apply=False)[0]
    assert item["action"] == "worktree_remove", item
    # The same for a full clone, whose own .git folder sits inside the entry.
    clone = cache / "scratch" / "old-clone"
    git("clone", str(repo.parent.parent / "origin.git"), str(clone))
    age(clone, 10)
    (clone / ".git" / "index").touch()
    os.utime(clone / ".git")
    item = gc.run([clone], cache_dir=cache, min_idle_days=7, apply=False)[0]
    assert item["action"] == "remove", item
    # A scan must not touch the index itself (git status --no-optional-locks).
    before = (clone / ".git").stat().st_mtime
    gc.run([clone], cache_dir=cache, min_idle_days=7, apply=False)
    assert (clone / ".git").stat().st_mtime == before


@pytest.mark.parametrize("change", ["modified", "untracked", "unpushed"])
def test_worktree_with_unsaved_work_is_kept(gc, cache: Path, repo: Path, change: str):
    wt = add_worktree(repo, cache, "busy", push=(change != "unpushed"))
    if change == "modified":
        (wt / "busy.txt").write_text("edited\n", encoding="utf-8")
    elif change == "untracked":
        (wt / "new.txt").write_text("new\n", encoding="utf-8")
    age(wt, 30)
    item = gc.run([wt], cache_dir=cache, min_idle_days=7, apply=True)[0]
    assert item["action"] == "keep"
    expected = "not on any remote" if change == "unpushed" else "uncommitted or untracked"
    assert any(expected in r for r in item["reasons"]), item["reasons"]
    assert wt.exists()


def test_unpushed_worktree_with_merged_pr_at_head_can_go(gc, cache: Path, repo: Path, monkeypatch):
    wt = add_worktree(repo, cache, "squashed", push=False)
    head = git("rev-parse", "HEAD", cwd=wt)
    monkeypatch.setattr(gc, "merged_pr_at", lambda path, h: "https://example.invalid/pr/1" if h == head else None)
    item = gc.run([wt], cache_dir=cache, min_idle_days=None, apply=False)[0]
    assert item["action"] == "worktree_remove", item
    # One more local commit after the merged head is real work again.
    (wt / "more.txt").write_text("more\n", encoding="utf-8")
    git("add", ".", cwd=wt)
    git("commit", "-m", "after merge", cwd=wt)
    item = gc.run([wt], cache_dir=cache, min_idle_days=None, apply=False)[0]
    assert item["action"] == "keep"


def test_scratch_with_nested_clone_work_is_kept(gc, cache: Path, repo: Path):
    folder = cache / "scratch" / "copy"
    (folder / "deep").mkdir(parents=True)
    clone = folder / "deep" / "widget"
    git("clone", str(repo.parent.parent / "origin.git"), str(clone))
    (clone / "local.txt").write_text("local\n", encoding="utf-8")
    git("add", ".", cwd=clone)
    git("commit", "-m", "local only", cwd=clone)
    age(folder, 30)
    item = gc.run([folder], cache_dir=cache, min_idle_days=7, apply=True)[0]
    assert item["action"] == "keep"
    assert any("copy/deep/widget" in r and "not on any remote" in r for r in item["reasons"]), item["reasons"]
    assert clone.exists()


def test_scratch_clone_with_stash_is_kept(gc, cache: Path, repo: Path):
    clone = cache / "scratch" / "stashy"
    git("clone", str(repo.parent.parent / "origin.git"), str(clone))
    (clone / "README.md").write_text("changed\n", encoding="utf-8")
    git("stash", cwd=clone)
    age(clone, 30)
    item = gc.run([clone], cache_dir=cache, min_idle_days=7, apply=True)[0]
    assert item["action"] == "keep"
    assert any("stash" in r for r in item["reasons"])


def test_process_inside_keeps_entry(gc, cache: Path, monkeypatch):
    folder = scratch_dir(cache, "running")
    age(folder, 30)
    cwd = gc.drc._norm(folder / "sub")
    monkeypatch.setattr(gc, "process_cwds", lambda: [(4242, "node", cwd)])
    item = gc.run([folder], cache_dir=cache, min_idle_days=7, apply=True)[0]
    assert item["action"] == "keep"
    assert any("node (pid 4242)" in r for r in item["reasons"])
    assert folder.exists()


def test_sibling_with_shared_prefix_is_not_busy(gc, cache: Path, monkeypatch):
    folder = scratch_dir(cache, "ns")
    age(folder, 30)
    other = gc.drc._norm(cache / "scratch" / "ns-smart")
    monkeypatch.setattr(gc, "process_cwds", lambda: [(1, "node", other)])
    assert gc.run([folder], cache_dir=cache, min_idle_days=7, apply=False)[0]["action"] == "remove"


def test_no_lsof_means_nothing_is_removed(gc, cache: Path, monkeypatch):
    folder = scratch_dir(cache, "unknown")
    age(folder, 30)
    monkeypatch.setattr(gc, "process_cwds", lambda: None)
    item = gc.run([folder], cache_dir=cache, min_idle_days=7, apply=True)[0]
    assert item["action"] == "keep"
    assert any("lsof unavailable" in r for r in item["reasons"])


def test_locked_worktree_and_keep_marker_are_kept(gc, cache: Path, repo: Path):
    wt = add_worktree(repo, cache, "audit-hold")
    git("worktree", "lock", "--reason", "audit; release 2026-12-01", str(wt), cwd=repo)
    folder = scratch_dir(cache, "pinned")
    (folder / ".acs-keep").write_text("", encoding="utf-8")
    for p in (wt, folder):
        age(p, 30)
    items = by_name(gc.run([wt, folder], cache_dir=cache, min_idle_days=7, apply=True))
    assert any("locked: audit" in r for r in items["audit-hold"]["reasons"])
    assert any(".acs-keep" in r for r in items["pinned"]["reasons"])
    assert wt.exists() and folder.exists()


def test_worktree_whose_main_repo_is_gone_is_kept(gc, cache: Path, repo: Path):
    wt = add_worktree(repo, cache, "orphan")
    shutil.rmtree(repo)
    age(wt, 30)
    item = gc.run([wt], cache_dir=cache, min_idle_days=7, apply=True)[0]
    assert item["action"] == "keep"
    assert any("git cannot read" in r for r in item["reasons"])


def test_recheck_before_removal_catches_a_new_session(gc, cache: Path, monkeypatch):
    folder = scratch_dir(cache, "race")
    age(folder, 30)
    calls = iter([[], [(7, "claude", gc.drc._norm(folder))]])
    monkeypatch.setattr(gc, "process_cwds", lambda: next(calls))
    item = gc.run([folder], cache_dir=cache, min_idle_days=7, apply=True)[0]
    assert item["action"] == "keep"
    assert item["reasons"][0] == "changed since the scan"
    assert folder.exists()


# ---------------------------------------------------------------- finish


def test_finish_removes_task_worktree_and_scratch_regardless_of_age(gc, cache: Path, repo: Path):
    wt = add_worktree(repo, cache, "just-merged")
    folder = scratch_dir(cache, "just-merged")
    items = gc.run([wt, folder], cache_dir=cache, min_idle_days=None, apply=True)
    assert all(i.get("done") for i in items), items
    assert not wt.exists() and not folder.exists()


def test_finish_refuses_paths_outside_the_cache(gc, cache: Path, repo: Path, tmp_path: Path):
    deps = cache / "deps" / "pcm"
    deps.mkdir()
    nested = scratch_dir(cache, "outer") / "sub"
    items = gc.run([repo, deps, nested, tmp_path / "missing"], cache_dir=cache, min_idle_days=None, apply=True)
    assert all(i["action"] == "keep" for i in items)
    assert repo.exists() and deps.exists() and nested.exists()


def test_cli_finish_dry_run_and_json(gc, cache: Path, repo: Path, capsys):
    wt = add_worktree(repo, cache, "cli-task")
    rc = gc.main(["--no-gh", "finish", str(wt), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0 and "REMOVE" in out and "Nothing was changed" in out
    assert wt.exists()
    rc = gc.main(["--json", "--no-gh", "gc", "--days", "7"])
    report = json.loads(capsys.readouterr().out)
    assert rc == 0 and report["mode"] == "dry-run"
    assert by_name(report["items"])["cli-task"]["action"] == "keep"  # too recent for gc


# ---------------------------------------------------------------- real probe


@pytest.mark.skipif(shutil.which("lsof") is None or sys.platform == "win32", reason="needs lsof")
def test_real_lsof_sees_a_process_cwd(tmp_path: Path):
    mod = _load()
    busy = tmp_path / "busy"
    busy.mkdir()
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], cwd=str(busy))
    try:
        deadline = time.time() + 10
        found: list[str] = []
        while time.time() < deadline and not found:
            cwds = mod.process_cwds()
            assert cwds is not None
            found = mod.processes_inside(busy, cwds)
        assert any(f"pid {proc.pid}" in f for f in found), found
    finally:
        proc.kill()
        proc.wait()
