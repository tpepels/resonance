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


def test_app_review_summary_action(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()

    args = _base_args(tmp_path, library_root=library)
    service = ResonanceService()

    inputs = iter(["11", "q"])
    captured: list[str] = []

    code = run_app(
        args,
        service=service,
        input_provider=lambda prompt: next(inputs),
        output_sink=captured.append,
    )

    assert code == 0
    assert any(line.startswith("review:") for line in captured)


def test_app_apply_cancelled_when_not_confirmed(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()

    args = _base_args(tmp_path, library_root=library)
    service = ResonanceService()

    # choose apply -> provide plan path -> deny confirmation -> quit
    inputs = iter(["6", str(tmp_path / "plan.json"), "n", "q"])
    captured: list[str] = []

    code = run_app(
        args,
        service=service,
        input_provider=lambda prompt: next(inputs),
        output_sink=captured.append,
    )

    assert code == 0
    assert any("apply: cancelled" in line for line in captured)
