"""Agent wiring (Refs #112): an install must put its rules in front of Claude Code.

Claude Code reads only ``CLAUDE.md``. The installer therefore writes a
``CLAUDE.md`` that imports ``AGENTS.md`` and adds one marker-delimited block to
``AGENTS.md`` that names the hotload rules. ``hotload_check`` fails an installed
adopter whose wiring is missing, so ``READY`` cannot mean "rules inactive".
"""

from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
CHECK = MODULE_ROOT / "scripts" / "hotload_check.py"

START = "<!-- acs:boot:start -->"
END = "<!-- acs:boot:end -->"
HSW_TEXT = "CGM ALWAYS-ON WRITING RULE (fixture)"


def _hotload_check():
    spec = spec_from_file_location("hotload_check", CHECK)
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _install(installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
             stub_externals, run_args, *, routing: bool = False, adopter=None):
    stub_externals()
    adopter = adopter or make_adopter()
    pcm, cgm = make_checkouts()
    if routing:
        (cgm / "docs").mkdir(exist_ok=True)
        (cgm / "docs" / "writing-routing.json").write_text(
            json.dumps({"acs_prompt_inject": {"system_block": HSW_TEXT}}), encoding="utf-8"
        )
    rc = installer.run(run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout()))
    return rc, adopter


def test_install_writes_claude_md_that_imports_agents_md(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    rc, adopter = _install(installer, make_acs_root, make_adopter, make_checkouts,
                           make_oio_checkout, stub_externals, run_args)
    assert rc == 0
    lines = (adopter / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    assert "@AGENTS.md" in lines


def test_install_adds_boot_block_to_agents_md(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    rc, adopter = _install(installer, make_acs_root, make_adopter, make_checkouts,
                           make_oio_checkout, stub_externals, run_args, routing=True)
    assert rc == 0
    text = (adopter / "AGENTS.md").read_text(encoding="utf-8")
    assert text.count(START) == 1 and text.count(END) == 1
    block = text[text.index(START):text.index(END)]
    assert "HOTLOAD.md" in block
    assert HSW_TEXT in block          # always-on writing block, inlined from the CGM pin
    assert "~/.cache/acs" in block    # dev-root rule


def test_boot_block_points_at_cgm_source_when_routing_is_unreadable(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    rc, adopter = _install(installer, make_acs_root, make_adopter, make_checkouts,
                           make_oio_checkout, stub_externals, run_args, routing=False)
    assert rc == 0
    text = (adopter / "AGENTS.md").read_text(encoding="utf-8")
    assert "writing-routing.json" in text[text.index(START):text.index(END)]


def test_existing_user_content_is_preserved(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    adopter = make_adopter()
    (adopter / "CLAUDE.md").write_text("# My rules\nUse tabs.\n", encoding="utf-8")
    (adopter / "AGENTS.md").write_text("# Agents\nBe kind.\n", encoding="utf-8")
    rc, _ = _install(installer, make_acs_root, make_adopter, make_checkouts,
                     make_oio_checkout, stub_externals, run_args, adopter=adopter)
    assert rc == 0
    claude = (adopter / "CLAUDE.md").read_text(encoding="utf-8")
    agents = (adopter / "AGENTS.md").read_text(encoding="utf-8")
    assert claude.startswith("# My rules\nUse tabs.\n")
    assert claude.splitlines().count("@AGENTS.md") == 1
    assert agents.startswith("# Agents\nBe kind.\n")
    assert START in agents


def test_install_is_idempotent(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    stub_externals()
    acs, adopter = make_acs_root(), make_adopter()
    pcm, cgm = make_checkouts()
    oio = make_oio_checkout()
    assert installer.run(run_args(acs, adopter, pcm, cgm, oio)) == 0
    first = {n: (adopter / n).read_bytes() for n in ("CLAUDE.md", "AGENTS.md")}
    assert installer.run(run_args(acs, adopter, pcm, cgm, oio)) == 0
    for name, before in first.items():
        assert (adopter / name).read_bytes() == before, name


def test_stale_block_is_replaced_in_place_not_duplicated(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    adopter = make_adopter()
    (adopter / "AGENTS.md").write_text(
        f"# Top\n{START}\nold text\n{END}\n# Bottom\n", encoding="utf-8"
    )
    rc, _ = _install(installer, make_acs_root, make_adopter, make_checkouts,
                     make_oio_checkout, stub_externals, run_args, adopter=adopter)
    assert rc == 0
    text = (adopter / "AGENTS.md").read_text(encoding="utf-8")
    assert text.count(START) == 1
    assert "old text" not in text
    assert text.startswith("# Top\n") and text.rstrip().endswith("# Bottom")


def test_dry_run_writes_no_wiring(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args,
):
    stub_externals()
    adopter = make_adopter()
    pcm, cgm = make_checkouts()
    rc = installer.run(run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout(), dry_run=True))
    assert rc == 0
    assert not (adopter / "CLAUDE.md").exists()
    assert not (adopter / "AGENTS.md").exists()


def test_failed_hotload_check_rolls_wiring_back(
    installer, make_acs_root, make_adopter, make_checkouts, make_oio_checkout,
    stub_externals, run_args, monkeypatch,
):
    stub_externals()
    monkeypatch.setattr(
        installer, "run_script",
        lambda argv: 1 if "hotload_check.py" in " ".join(argv) else 0,
    )
    adopter = make_adopter()
    (adopter / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    pcm, cgm = make_checkouts()
    rc = installer.run(run_args(make_acs_root(), adopter, pcm, cgm, make_oio_checkout()))
    assert rc == 1
    assert (adopter / "AGENTS.md").read_text(encoding="utf-8") == "# Agents\n"
    assert not (adopter / "CLAUDE.md").exists()


# --- hotload_check: absent wiring is a failure ---------------------------------


def _installed_adopter(tmp_path: Path) -> Path:
    adopter = tmp_path / "installed"
    (adopter / ".coord").mkdir(parents=True)
    (adopter / ".coord" / "hotload.lock.json").write_text("{}", encoding="utf-8")
    return adopter


def test_check_fails_when_claude_md_is_missing(tmp_path: Path):
    mod = _hotload_check()
    adopter = _installed_adopter(tmp_path)
    (adopter / "AGENTS.md").write_text(f"{START}\nHOTLOAD.md\n{END}\n", encoding="utf-8")
    errors = mod.check_agent_wiring(adopter)
    assert any("CLAUDE.md" in e for e in errors), errors


def test_check_fails_when_boot_block_is_missing(tmp_path: Path):
    mod = _hotload_check()
    adopter = _installed_adopter(tmp_path)
    (adopter / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (adopter / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    errors = mod.check_agent_wiring(adopter)
    assert any("acs:boot" in e for e in errors), errors


def test_check_passes_on_wired_adopter_and_skips_non_adopters(tmp_path: Path):
    mod = _hotload_check()
    adopter = _installed_adopter(tmp_path)
    (adopter / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (adopter / "AGENTS.md").write_text(
        f"{START}\nsee HOTLOAD.md\n{mod.DEV_ROOT_RULE}\n{END}\n", encoding="utf-8"
    )
    assert mod.check_agent_wiring(adopter) == []
    # A tree with no hotload lock is not an installed adopter (e.g. the ACS repo itself).
    assert mod.check_agent_wiring(tmp_path / "nowhere") == []


def test_run_returns_nonzero_for_unwired_installed_adopter(tmp_path: Path):
    mod = _hotload_check()
    adopter = _installed_adopter(tmp_path)
    rc = mod.run(MODULE_ROOT, skip_cgm_validate=True, adopter_root=adopter, dev_root=tmp_path)
    assert rc == 1
