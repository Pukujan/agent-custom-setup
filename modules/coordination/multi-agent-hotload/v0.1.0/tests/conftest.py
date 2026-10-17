"""Shared fixtures for the hotload install taxonomy (SPEC.md section 8).

The five install test modules (acceptance/PDD, states/SDD, gates/TDD,
metamorphic, manifest/differential) all drive the same installer against the
same fake world: a fixture ACS root, fake PCM/CGM/OIO checkouts, and stubbed
external checkers. Keeping that world here means the tests assert behaviour, not
scaffolding.

The seat-protocol fixtures at the bottom of this file (``seat_protocol``,
``claim_store``, ``clock``) are the same idea for the coordination runtime:
``claim_store`` is parametrised over the local-file store and the in-memory
store, so the protocol suite proves the state machine against the interface
rather than against one implementation.

No network and no pinned checkouts are needed; everything is offline and
cross-platform (Windows, macOS, Linux).
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = MODULE_ROOT / "scripts" / "acs_install.py"
SEAT_PROTOCOL = MODULE_ROOT / "scripts" / "seat_protocol.py"
MODULE_REL = "modules/coordination/multi-agent-hotload/v0.1.0"

PCM_SHA = "a" * 40
CGM_SHA = "b" * 40
ACS_SHA = "c" * 40
OIO_SHA = "d" * 40

CGM_MODULES = [
    "brand-foundation",
    "content-context",
    "writing-direction",
    "human-sounding-writing",
    "human-output-naming",
    "visual-direction",
    "image-generation",
    "html-demo",
]

PINS = {
    "pcm": {"cli_version": "0.6.0", "commit": PCM_SHA},
    "cgm": {"version": "0.5.12", "commit": CGM_SHA, "modules": list(CGM_MODULES)},
    "acs_hotload_module": {"id": "multi-agent-hotload", "version": "0.1.0"},
}


def load_installer():
    spec = spec_from_file_location("acs_install", SCRIPT)
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mesh_doc() -> dict:
    """A fixture mesh. The installer reads commits from here, never from pins.json."""
    return {
        "source": "fixture-train",
        "requires": {
            "project-continuity-modules": {"version": "0.6.0", "commit": PCM_SHA},
            "content-generation-modules": {"version": "0.5.12", "commit": CGM_SHA},
            "agent-custom-setup": {"version": "0.2.0", "commit": ACS_SHA},
            "observational-issue-ops": {"version": "0.1.0", "commit": OIO_SHA},
        },
    }


def git_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


@pytest.fixture
def installer():
    """A freshly loaded acs_install module (monkeypatch-safe, function-scoped)."""
    return load_installer()


@pytest.fixture
def make_acs_root(tmp_path: Path):
    def _make(mesh: dict | None = None) -> Path:
        root = tmp_path / "acs"
        pack = root / MODULE_REL
        pack.mkdir(parents=True)
        (pack / "pins.json").write_text(json.dumps({"pins": PINS}), encoding="utf-8")
        (root / "stack-mesh.json").write_text(
            json.dumps(mesh if mesh is not None else mesh_doc()), encoding="utf-8"
        )
        return root

    return _make


@pytest.fixture
def make_adopter(tmp_path: Path):
    def _make(name: str = "adopter", *, with_adapter: bool = True) -> Path:
        adopter = tmp_path / name
        adopter.mkdir()
        if with_adapter:
            (adopter / ".content-system").mkdir()
        return adopter

    return _make


@pytest.fixture
def make_checkouts(tmp_path: Path):
    def _make() -> tuple[Path, Path]:
        pcm = tmp_path / "pcm-ck"
        cgm = tmp_path / "cgm-ck"
        pcm.mkdir()
        cgm.mkdir()
        return pcm, cgm

    return _make


@pytest.fixture
def make_oio_checkout(tmp_path: Path):
    def _make() -> Path:
        oio = tmp_path / "oio-ck"
        (oio / ".github" / "scripts").mkdir(parents=True)
        (oio / ".github" / "scripts" / "oio_installer.py").write_text("# stub\n", encoding="utf-8")
        return oio

    return _make


@pytest.fixture
def stub_externals(monkeypatch, installer):
    """Make check_pins/hotload_check succeed and report the pinned HEADs."""

    def _stub(*, oio_supported: bool = True) -> None:
        def fake_git_head(root):
            return {
                "pcm-ck": PCM_SHA,
                "cgm-ck": CGM_SHA,
                "oio-ck": OIO_SHA,
            }.get(Path(root).name, ACS_SHA)

        monkeypatch.setattr(installer, "git_head", fake_git_head)
        monkeypatch.setattr(installer, "run_script", lambda argv: 0)
        monkeypatch.setattr(
            installer,
            "oio_platform_supported",
            lambda *_: (True, "") if oio_supported else (False, "os.O_NOFOLLOW is unavailable"),
        )

    return _stub


@pytest.fixture
def run_args(installer):
    def _make(acs_root, adopter, pcm, cgm, oio=None, **over):
        base = dict(
            adopter_root=adopter,
            acs_root=acs_root,
            pcm_root=pcm,
            cgm_root=cgm,
            oio_root=oio,
            project_name=None,
            project_id=None,
            dry_run=False,
            force=False,
        )
        base.update(over)
        return installer.argparse.Namespace(**base)

    return _make


# ---------------------------------------------------------------------------
# Seat-protocol fixtures (tests/test_coordination*.py)


def load_seat_protocol():
    """Load ``scripts/seat_protocol.py`` the way the pack loads its scripts."""
    spec = spec_from_file_location("seat_protocol", SEAT_PROTOCOL)
    assert spec and spec.loader
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def seat_protocol():
    """A freshly loaded seat_protocol module (function-scoped)."""
    return load_seat_protocol()


@pytest.fixture(params=["local_file", "in_memory"])
def claim_store(seat_protocol, tmp_path, request):
    """The seat store under test, parametrised over both implementations.

    Running the same suite against the local-file store and the in-memory
    store is what proves the state machine is written against the
    ``ClaimStore`` interface rather than one implementation — the abstraction
    the authoritative-store question rests on.
    """
    if request.param == "local_file":
        return seat_protocol.LocalFileClaimStore(tmp_path / "boss_claim.json")
    return seat_protocol.InMemoryClaimStore()


@pytest.fixture
def machine(seat_protocol, claim_store):
    """A SeatMachine over the parametrised store at the default 30m lease."""
    return seat_protocol.SeatMachine(claim_store, lease_ttl_minutes=30)


@pytest.fixture
def clock():
    """A deterministic clock: starts 2026-10-13T12:00Z, ``advance`` moves it."""

    class _Clock:
        def __init__(self):
            self.now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)

        def advance(self, minutes: float) -> datetime:
            self.now = self.now + timedelta(minutes=minutes)
            return self.now

        def at(self, minutes: float = 0.0) -> datetime:
            return self.now + timedelta(minutes=minutes)

    return _Clock()
