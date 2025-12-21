"""CLI entrypoint smoke tests."""

from __future__ import annotations

import subprocess
import sys


def test_cli_entrypoint_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "resonance.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "usage: resonance" in result.stdout.lower()
