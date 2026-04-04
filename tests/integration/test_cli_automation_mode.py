"""Automation/admin CLI behavior tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_prompt_automation_requires_scripted_input(tmp_path: Path) -> None:
    state_db = tmp_path / "state.db"
    # create db file via scan to ensure path is valid
    library = tmp_path / "library"
    library.mkdir()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "resonance.cli",
            "scan",
            str(library),
            "--state-db",
            str(state_db),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "resonance.cli",
            "prompt",
            "--state-db",
            str(state_db),
            "--mode",
            "automation",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "prompt requires --decisions-file or --replay-file" in result.stderr


def test_cli_decide_admin_headless_works_on_empty_library(tmp_path: Path) -> None:
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
            "admin",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["command"] == "decide"
