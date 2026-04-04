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


def test_cli_resolve_fail_on_warning_returns_nonzero_when_prompt_needed(tmp_path: Path) -> None:
    library = tmp_path / "library"
    album = library / "album"
    album.mkdir(parents=True)
    # Create minimal audio stubs with no provider credentials; resolve will process NEW dir
    (album / "01 Track.flac").write_bytes(b"\x00")
    state_db = tmp_path / "state.db"

    scan_result = subprocess.run(
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
    assert scan_result.returncode == 0

    resolve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "resonance.cli",
            "resolve",
            str(library),
            "--state-db",
            str(state_db),
            "--mode",
            "automation",
            "--fail-on-warning",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert resolve_result.returncode == 1
