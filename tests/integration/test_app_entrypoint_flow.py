"""Integration tests for unified app entrypoint flow."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from resonance.api.service import ResonanceService
from resonance.commands.app import run_app


def test_app_entrypoint_shows_status_and_quits(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    state_db = tmp_path / "state.db"

    args = Namespace(
        command="app",
        library_root=library,
        state_db=state_db,
        cache_db=None,
        offline=False,
        plan_dir=None,
        auto_probable=False,
        auto_probable_min_gap=0.15,
        json=False,
    )

    service = ResonanceService()
    captured: list[str] = []
    inputs = iter(["q"])

    code = run_app(
        args,
        service=service,
        input_provider=lambda prompt: next(inputs),
        output_sink=captured.append,
    )

    assert code == 0
    assert any(line.startswith("status:") for line in captured)
    assert any("Choose action:" in line for line in captured)
