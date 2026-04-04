"""Tests for unified app entrypoint command."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from resonance.api.service import ResonanceService
from resonance.commands.app import run_app


def _base_args(tmp_path: Path, **overrides) -> Namespace:
    defaults = dict(
        command="app",
        library_root=tmp_path / "library",
        state_db=tmp_path / "state.db",
        cache_db=None,
        offline=False,
        plan_dir=None,
        auto_probable=False,
        auto_probable_min_gap=0.15,
        json=False,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


def test_app_quit_immediately(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()

    args = _base_args(tmp_path, library_root=library)
    service = ResonanceService()

    inputs = iter(["q"])
    captured: list[str] = []

    code = run_app(
        args,
        service=service,
        input_provider=lambda prompt: next(inputs),
        output_sink=captured.append,
    )

    assert code == 0
    assert any("Resonance App" in line for line in captured)
    assert any("bye" in line for line in captured)
