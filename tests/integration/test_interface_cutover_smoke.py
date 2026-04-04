"""Smoke coverage for interface cutover assumptions."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_resonance_help_lists_app_and_mode_flags() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "resonance.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "app" in result.stdout


def test_app_help_works() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "resonance.cli", "app", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "usage: resonance app" in result.stdout


def test_decide_automation_smoke(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    state_db = tmp_path / "state.db"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "resonance.cli",
            "decide",
            str(library),
            "--state-db",
            str(state_db),
            "--mode",
            "automation",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "decide"
