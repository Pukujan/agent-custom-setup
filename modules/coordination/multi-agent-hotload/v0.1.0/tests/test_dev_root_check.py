"""Tests for dev_root_check.py and its wiring into hotload_check.py.

Every test builds a fake dev root under tmp_path and points ACS_CACHE_DIR at
tmp_path too, so nothing on the real machine is read or changed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = MODULE_ROOT / "scripts"
DRC_SCRIPT = SCRIPTS / "dev_root_check.py"

GIT_CFG = [
    "-c", "user.name=ACS Test",
    "-c", "user.email=acs-test@example.invalid",
    "-c", "commit.gpgsign=false",
    "-c", "init.defaultBranch=main",
    "-c", "core.autocrlf=false",
]


def _load(name: str):
    spec = spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *GIT_CFG, *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stdout}{proc.stderr}"
    return proc.stdout.strip()


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ACS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("ACS_DEV_ROOT", raising=False)
    monkeypatch.delenv("ACS_DEV_ROOT_STRICT", raising=False)
    monkeypatch.delenv("CGM_ROOT", raising=False)


@pytest.fixture()
def remote(tmp_path: Path) -> Path:
    """A bare 'origin' with one commit on main."""
    bare = tmp_path / "remotes" / "widget.git"
    bare.parent.mkdir(parents=True)
    git("init", "--bare", str(bare))
    seed = tmp_path / "seed"
    git("clone", str(bare), str(seed))
    (seed / "README.md").write_text("widget\n", encoding="utf-8")
    git("add", "README.md", cwd=seed)
    git("commit", "-m", "init", cwd=seed)
    git("push", "origin", "HEAD:main", cwd=seed)
    return bare


def make_dev_root(tmp_path: Path) -> Path:
    root = tmp_path / "dev"
    root.mkdir()
    return root


def clone(remote: Path, dest: Path) -> Path:
    git("clone", str(remote), str(dest))
    return dest


def run_cli(*args: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(DRC_SCRIPT), *args], capture_output=True, text=True, check=False
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise AssertionError(f"not JSON (exit {proc.returncode}): {proc.stdout}{proc.stderr}")
    return proc.returncode, data


def kinds(report: dict) -> dict[str, str]:
    return {f["name"]: f["kind"] for f in report["findings"]}


# ---------------------------------------------------------------- scan


def test_clean_root_exits_zero(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    clone(remote, root / "widget")
    code, data = run_cli("--dev-root", str(root))
    assert code == 0, data
    assert data["ok"] is True
    assert data["findings"] == []
    assert data["primary_checkouts"] == ["widget"]


def test_missing_dev_root_exits_two(tmp_path: Path):
    code, data = run_cli("--dev-root", str(tmp_path / "nope"))
    assert code == 2
    assert data["ok"] is False


def test_flags_non_git_dot_dep_and_stray_entries(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    clone(remote, root / "widget")
    (root / "notes").mkdir()
    (root / ".scratch" / "probe").mkdir(parents=True)
    (root / "_deps" / "cgm").mkdir(parents=True)
    (root / "node_modules").mkdir()
    (root / "todo.txt").write_text("x", encoding="utf-8")
    code, data = run_cli("--dev-root", str(root))
    assert code == 1
    k = kinds(data)
    assert k["notes"] == "not_git"
    assert k[".scratch"] == "dot_or_dep_folder"
    assert k["_deps"] == "dot_or_dep_folder"
    assert k["node_modules"] == "cache_folder"
    assert k["todo.txt"] == "stray_file"
    assert "widget" not in k


def test_flags_linked_worktree_at_top_level(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    repo = clone(remote, root / "widget")
    git("worktree", "add", "-b", "feature", str(root / "widget-wt"), cwd=repo)
    mod = _load("dev_root_check")
    report = mod.scan(root)
    k = kinds(report)
    assert k == {"widget-wt": "linked_worktree"}
    finding = report["findings"][0]
    assert Path(finding["registered_by"]).name == "widget"


def test_flags_duplicate_clone_and_keeps_the_one_named_after_the_remote(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    clone(remote, root / "widget")
    clone(remote, root / "widget-copy")
    mod = _load("dev_root_check")
    report = mod.scan(root)
    assert kinds(report) == {"widget-copy": "duplicate_clone"}
    assert report["primary_checkouts"] == ["widget"]


def test_flags_worktree_registered_inside_a_checkout(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    repo = clone(remote, root / "widget")
    nested = repo / ".worktrees" / "fix"
    git("worktree", "add", "-b", "fix", str(nested), cwd=repo)
    mod = _load("dev_root_check")
    report = mod.scan(root)
    assert [f["kind"] for f in report["findings"]] == ["registered_worktree"]
    assert Path(report["findings"][0]["path"]).name == "fix"


def test_worktree_outside_dev_root_is_fine(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    repo = clone(remote, root / "widget")
    git("worktree", "add", "-b", "outside", str(tmp_path / "cache" / "worktrees" / "widget-outside"), cwd=repo)
    mod = _load("dev_root_check")
    assert mod.scan(root)["ok"] is True


def test_normalize_remote_matches_https_and_ssh():
    mod = _load("dev_root_check")
    a = mod.normalize_remote("https://github.com/Pukujan/Widget.git")
    b = mod.normalize_remote("git@github.com:Pukujan/widget")
    assert a == b == "github.com/pukujan/widget"


# ---------------------------------------------------------------- clean


def _junk_root(tmp_path: Path, remote: Path) -> Path:
    root = make_dev_root(tmp_path)
    repo = clone(remote, root / "widget")
    (root / ".scratch" / "probe").mkdir(parents=True)
    (root / ".scratch" / "probe" / "out.txt").write_text("probe", encoding="utf-8")
    git("worktree", "add", "-b", "feature", str(root / "widget-wt"), cwd=repo)
    git("push", "origin", "feature", cwd=root / "widget-wt")
    return root


def test_clean_is_a_dry_run_without_yes(tmp_path: Path, remote: Path):
    root = _junk_root(tmp_path, remote)
    before = sorted(p.name for p in root.iterdir())
    code, data = run_cli("--dev-root", str(root), "--clean")
    assert code == 1
    assert data["clean"]["mode"] == "dry-run"
    actions = {Path(a["path"]).name: a["action"] for a in data["clean"]["actions"]}
    assert actions == {".scratch": "move", "widget-wt": "worktree_remove"}
    assert sorted(p.name for p in root.iterdir()) == before
    assert not (tmp_path / "cache").exists()


def test_clean_yes_moves_junk_to_cache_and_removes_clean_worktree(tmp_path: Path, remote: Path):
    root = _junk_root(tmp_path, remote)
    code, data = run_cli("--dev-root", str(root), "--clean", "--yes")
    assert code == 0, json.dumps(data, indent=2)
    assert sorted(p.name for p in root.iterdir()) == ["widget"]
    assert (tmp_path / "cache" / "scratch" / "scratch" / "probe" / "out.txt").is_file()
    assert "widget-wt" not in git("worktree", "list", cwd=root / "widget")
    assert data["after"]["ok"] is True


def test_clean_refuses_dirty_unpushed_and_stashed_work(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    repo = clone(remote, root / "widget")

    dirty = clone(remote, root / "widget-dirty")
    (dirty / "README.md").write_text("changed\n", encoding="utf-8")

    unpushed = clone(remote, root / "widget-unpushed")
    (unpushed / "new.txt").write_text("new\n", encoding="utf-8")
    git("add", "new.txt", cwd=unpushed)
    git("commit", "-m", "local only", cwd=unpushed)

    stashed = clone(remote, root / "widget-stashed")
    (stashed / "README.md").write_text("stash me\n", encoding="utf-8")
    git("stash", cwd=stashed)

    # A scratch folder hiding a clone with unpushed work must be refused too.
    hidden = root / ".scratch" / "widget"
    hidden.parent.mkdir()
    clone(remote, hidden)
    (hidden / "x.txt").write_text("x\n", encoding="utf-8")
    git("add", "x.txt", cwd=hidden)
    git("commit", "-m", "hidden work", cwd=hidden)

    git("worktree", "add", "-b", "wip", str(root / "widget-wt"), cwd=repo)
    (root / "widget-wt" / "wip.txt").write_text("wip\n", encoding="utf-8")

    code, data = run_cli("--dev-root", str(root), "--clean", "--yes")
    assert code == 1
    actions = {Path(a["path"]).name: a["action"] for a in data["clean"]["actions"]}
    assert actions == {
        ".scratch": "refuse",
        "widget-dirty": "refuse",
        "widget-stashed": "refuse",
        "widget-unpushed": "refuse",
        "widget-wt": "refuse",
    }
    for name in actions:
        assert (root / name).exists(), name
    assert (hidden / "x.txt").is_file()


def test_clean_refuses_cache_dir_inside_dev_root(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    clone(remote, root / "widget")
    code, data = run_cli("--dev-root", str(root), "--cache-dir", str(root / ".acs-cache"), "--clean", "--yes")
    assert code == 2
    assert "inside the dev root" in data["error"]


def test_ensure_outside_dev_root(tmp_path: Path):
    mod = _load("dev_root_check")
    root = make_dev_root(tmp_path)
    with pytest.raises(mod.DevRootViolation):
        mod.ensure_outside_dev_root(root / "_deps" / "cgm", root)
    outside = tmp_path / "cache" / "deps" / "cgm"
    assert mod.ensure_outside_dev_root(outside, root) == outside


def test_default_cache_dir_honours_env(tmp_path: Path):
    mod = _load("dev_root_check")
    assert mod.default_cache_dir() == tmp_path / "cache"
    assert mod.cache_subdir("deps") == tmp_path / "cache" / "deps"
    with pytest.raises(ValueError):
        mod.cache_subdir("elsewhere")


# ---------------------------------------------------------------- hotload_check wiring


def _fake_cgm(path: Path) -> Path:
    (path / "scripts").mkdir(parents=True)
    (path / "scripts" / "validate_content_system.py").write_text("", encoding="utf-8")
    (path / "system-version.json").write_text("{}", encoding="utf-8")
    return path


def test_hotload_refuses_dependency_inside_dev_root(tmp_path: Path, remote: Path):
    hc = _load("hotload_check")
    root = make_dev_root(tmp_path)
    primary = clone(remote, root / "widget")
    assert hc.dependency_location_problem(primary, root) is None
    msg = hc.dependency_location_problem(root / "_deps" / "cgm", root)
    assert msg and "inside the dev root" in msg
    assert hc.dependency_location_problem(tmp_path / "cache" / "deps" / "cgm", root) is None


def test_hotload_discovery_prefers_cache_and_skips_dev_root_copies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hc = _load("hotload_check")
    root = make_dev_root(tmp_path)
    _fake_cgm(root / "_deps" / "cgm")
    cached = _fake_cgm(tmp_path / "cache" / "deps" / "content-generation-modules")
    found = hc.discover_cgm_root(None, dev_root=root)
    assert found == cached.resolve()
    # An explicit path inside the dev root is returned so run() can report it.
    explicit = hc.discover_cgm_root(root / "_deps" / "cgm", dev_root=root)
    assert explicit == (root / "_deps" / "cgm").resolve()


def test_hotload_warns_on_dev_root_findings(tmp_path: Path, remote: Path, capsys: pytest.CaptureFixture[str]):
    hc = _load("hotload_check")
    root = make_dev_root(tmp_path)
    clone(remote, root / "widget")
    (root / ".scratch").mkdir()
    rc = hc.run(MODULE_ROOT, skip_cgm_validate=True, dev_root=root)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "hotload_check: WARN dev_root: dot_or_dep_folder" in out
    assert "ACS dev root rule" in out


def test_hotload_strict_dev_root_fails(tmp_path: Path, remote: Path, capsys: pytest.CaptureFixture[str]):
    hc = _load("hotload_check")
    root = make_dev_root(tmp_path)
    clone(remote, root / "widget")
    (root / ".scratch").mkdir()
    rc = hc.run(MODULE_ROOT, skip_cgm_validate=True, dev_root=root, strict_dev_root=True)
    out = capsys.readouterr().out
    assert rc == 1
    assert "hotload_check: FAIL" in out
    assert "dot_or_dep_folder" in out


def test_hotload_clean_dev_root_has_no_warning(tmp_path: Path, remote: Path, capsys: pytest.CaptureFixture[str]):
    hc = _load("hotload_check")
    root = make_dev_root(tmp_path)
    clone(remote, root / "widget")
    rc = hc.run(MODULE_ROOT, skip_cgm_validate=True, dev_root=root, strict_dev_root=True)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "WARN dev_root" not in out


def test_prompt_inject_render_carries_dev_root_rule():
    hc = _load("hotload_check")
    md = hc.render_prompt_inject_md(
        {"acs_prompt_inject": {"instruction": "x", "system_block": "y"}},
        pin_sha=hc.CGM_PIN_REVISION,
        pin_version=hc.CGM_PIN_VERSION,
    )
    assert "dev root hygiene" in md
    assert hc.DEV_ROOT_RULE in md
    committed = (MODULE_ROOT / "PROMPT_INJECT.md").read_text(encoding="utf-8")
    assert hc.DEV_ROOT_RULE in committed
    for doc in ("HOTLOAD.md", "BEHAVIOR.md"):
        assert "Dev root hygiene (binding)" in (MODULE_ROOT / doc).read_text(encoding="utf-8")


# ---------------------------------------------------------------- project-folder layout


def project(remote: Path, root: Path, name: str = "widget") -> Path:
    """<root>/<name>/main as a clone of ``remote``; returns the main checkout."""
    (root / name).mkdir()
    return clone(remote, root / name / "main")


@pytest.fixture()
def other_remote(tmp_path: Path) -> Path:
    bare = tmp_path / "remotes" / "gadget.git"
    bare.parent.mkdir(parents=True, exist_ok=True)
    git("init", "--bare", str(bare))
    seed = tmp_path / "seed-gadget"
    git("clone", str(bare), str(seed))
    (seed / "README.md").write_text("gadget\n", encoding="utf-8")
    git("add", "README.md", cwd=seed)
    git("commit", "-m", "init", cwd=seed)
    git("push", "origin", "HEAD:main", cwd=seed)
    return bare


def test_project_folder_with_worktrees_and_flat_checkout_are_clean(tmp_path: Path, remote: Path, other_remote: Path):
    root = make_dev_root(tmp_path)
    main = project(remote, root)
    git("worktree", "add", "-b", "task-1", str(root / "widget" / "worktrees" / "TASK-1"), cwd=main)
    git("worktree", "add", "-b", "task-2", str(root / "widget" / "worktrees" / "TASK-2"), cwd=main)
    clone(other_remote, root / "gadget")  # legacy flat checkout
    project(other_remote, root, "solo")  # a second entry for gadget -> duplicate
    mod = _load("dev_root_check")
    report = mod.scan(root)
    assert kinds(report) == {"solo": "duplicate_clone"}
    assert report["project_folders"] == ["widget"]
    assert report["flat_checkouts"] == ["gadget"]


def test_project_folder_alone_is_ok_via_cli(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    project(remote, root)
    code, data = run_cli("--dev-root", str(root))
    assert code == 0, data
    assert data["project_folders"] == ["widget"]


def test_project_folder_flags_extra_entries_and_bad_worktrees(tmp_path: Path, remote: Path, other_remote: Path):
    root = make_dev_root(tmp_path)
    main = project(remote, root)
    (root / "widget" / "notes").mkdir()
    (root / "widget" / "todo.txt").write_text("x", encoding="utf-8")
    wts = root / "widget" / "worktrees"
    wts.mkdir()
    (wts / "loose").mkdir()
    clone(remote, wts / "full-clone")
    gadget = clone(other_remote, tmp_path / "elsewhere" / "gadget")
    git("worktree", "add", "-b", "foreign", str(wts / "foreign"), cwd=gadget)
    git("worktree", "add", "-b", "ok", str(wts / "ok"), cwd=main)
    mod = _load("dev_root_check")
    k = kinds(mod.scan(root))
    assert k == {
        "notes": "project_extra_entry",
        "todo.txt": "project_extra_entry",
        "loose": "worktrees_entry_not_worktree",
        "full-clone": "worktrees_entry_not_worktree",
        "foreign": "foreign_worktree",
    }


def test_project_worktree_outside_worktrees_dir_is_flagged(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    main = project(remote, root)
    git("worktree", "add", "-b", "sib", str(root / "widget-sib"), cwd=main)  # sibling in dev root
    git("worktree", "add", "-b", "nest", str(main / "pcm" / "worktree" / "T-1"), cwd=main)  # nested
    git("worktree", "add", "-b", "cache", str(tmp_path / "cache" / "worktrees" / "c"), cwd=main)  # outside: fine
    mod = _load("dev_root_check")
    report = mod.scan(root)
    by_name = {f["name"]: f for f in report["findings"]}
    assert set(by_name) == {"widget-sib", "T-1"}
    assert by_name["widget-sib"]["kind"] == "linked_worktree"
    assert by_name["T-1"]["kind"] == "registered_worktree"
    assert Path(by_name["T-1"]["target"]) == root / "widget" / "worktrees" / "T-1"


def test_project_main_that_is_a_worktree_is_flagged(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    src = clone(remote, tmp_path / "elsewhere" / "widget")
    (root / "widget").mkdir()
    git("worktree", "add", "-b", "m", str(root / "widget" / "main"), cwd=src)
    mod = _load("dev_root_check")
    assert kinds(mod.scan(root)) == {"widget": "project_main_not_primary"}


def test_clean_moves_misplaced_project_worktrees_home(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    main = project(remote, root)
    git("worktree", "add", "-b", "sib", str(root / "widget-sib"), cwd=main)
    (root / "widget-sib" / "wip.txt").write_text("uncommitted\n", encoding="utf-8")
    git("worktree", "add", "-b", "nest", str(main / ".worktrees" / "n1"), cwd=main)
    code, data = run_cli("--dev-root", str(root), "--clean")
    assert code == 1
    actions = {Path(a["path"]).name: a["action"] for a in data["clean"]["actions"]}
    assert actions == {"widget-sib": "worktree_move", "n1": "worktree_move"}
    assert (root / "widget-sib").exists()  # dry run
    code, data = run_cli("--dev-root", str(root), "--clean", "--yes")
    assert code == 0, json.dumps(data, indent=2)
    assert sorted(p.name for p in root.iterdir()) == ["widget"]
    assert (root / "widget" / "worktrees" / "widget-sib" / "wip.txt").is_file()  # work kept
    listing = git("worktree", "list", cwd=main)
    assert "worktrees" in listing and "widget-sib" in listing


def test_clean_never_moves_project_main_or_valid_worktrees(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    main = project(remote, root)
    git("worktree", "add", "-b", "ok", str(root / "widget" / "worktrees" / "ok"), cwd=main)
    (root / "widget" / "stray").mkdir()
    code, data = run_cli("--dev-root", str(root), "--clean", "--yes")
    assert code == 0, json.dumps(data, indent=2)
    assert [Path(a["path"]).name for a in data["clean"]["actions"]] == ["stray"]
    assert (main / ".git").is_dir()
    assert (root / "widget" / "worktrees" / "ok" / ".git").is_file()
    assert not (root / "widget" / "stray").exists()


def test_migrate_dry_run_changes_nothing(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    repo = clone(remote, root / "widget")
    git("worktree", "add", "-b", "f1", str(root / "widget-f1"), cwd=repo)
    code, plan = run_cli("--dev-root", str(root), "--migrate", "widget")
    assert code == 0, plan
    assert plan["mode"] == "dry-run"
    assert [s["action"] for s in plan["steps"]] == [
        "rename", "mkdir", "rename", "worktree_repair", "worktree_move", "worktree_prune",
    ]
    assert (repo / ".git").is_dir()
    assert (root / "widget-f1").exists()


def test_migrate_yes_moves_checkout_and_worktrees(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    repo = clone(remote, root / "widget")
    git("worktree", "add", "-b", "f1", str(root / "widget-f1"), cwd=repo)
    git("push", "origin", "f1", cwd=root / "widget-f1")
    git("worktree", "add", "-b", "f2", str(repo / "pcm" / "worktree" / "T-2"), cwd=repo)
    git("push", "origin", "f2", cwd=repo / "pcm" / "worktree" / "T-2")
    code, plan = run_cli("--dev-root", str(root), "--migrate", "widget", "--yes")
    assert code == 0, json.dumps(plan, indent=2)
    main = root / "widget" / "main"
    assert (main / ".git").is_dir()
    assert (root / "widget" / "worktrees" / "widget-f1" / ".git").is_file()
    assert (root / "widget" / "worktrees" / "T-2" / ".git").is_file()
    assert sorted(p.name for p in root.iterdir()) == ["widget"]
    assert git("status", "--porcelain", cwd=root / "widget" / "worktrees" / "T-2") == ""
    listing = git("worktree", "list", "--porcelain", cwd=main)
    assert "prunable" not in listing
    mod = _load("dev_root_check")
    assert mod.scan(root)["ok"] is True


def test_migrate_refuses_dirty_or_unpushed_work(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    repo = clone(remote, root / "widget")
    git("worktree", "add", "-b", "local-only", str(root / "widget-wip"), cwd=repo)
    (root / "widget-wip" / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "a.txt", cwd=root / "widget-wip")
    git("commit", "-m", "not pushed", cwd=root / "widget-wip")
    code, plan = run_cli("--dev-root", str(root), "--migrate", "widget", "--yes")
    assert code == 1
    assert plan["ok"] is False and "refusing" in plan["error"]
    assert (repo / ".git").is_dir() and (root / "widget-wip").exists()


def test_migrate_rejects_non_flat_entries(tmp_path: Path, remote: Path):
    root = make_dev_root(tmp_path)
    project(remote, root)
    code, plan = run_cli("--dev-root", str(root), "--migrate", "widget")
    assert code == 1
    assert "not a flat primary checkout" in plan["error"]


def test_hotload_accepts_dependency_at_project_main(tmp_path: Path, remote: Path):
    hc = _load("hotload_check")
    root = make_dev_root(tmp_path)
    main = project(remote, root)
    assert hc.dependency_location_problem(main, root) is None
    assert hc.dependency_location_problem(root / "widget" / "worktrees" / "x", root)
