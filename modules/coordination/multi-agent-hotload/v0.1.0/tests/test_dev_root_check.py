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
        pin_sha=hc.mesh_component("content-generation-modules")["commit"],
        pin_version=hc.mesh_component("content-generation-modules")["version"],
    )
    assert "dev root hygiene" in md
    assert hc.DEV_ROOT_RULE in md
    committed = (MODULE_ROOT / "PROMPT_INJECT.md").read_text(encoding="utf-8")
    assert hc.DEV_ROOT_RULE in committed
    for doc in ("HOTLOAD.md", "BEHAVIOR.md"):
        assert "Dev root hygiene (binding)" in (MODULE_ROOT / doc).read_text(encoding="utf-8")
