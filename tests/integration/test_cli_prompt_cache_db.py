"""CLI regression test for prompt --cache-db provider client injection."""

from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path

def test_cli_prompt_with_cache_db(tmp_path: Path) -> None:
    # Create a dummy state DB and a dummy cache DB file
    state_db = tmp_path / "state.db"
    cache_db = tmp_path / "cache.db"
    library = tmp_path / "library"
    library.mkdir()
    cache_db.write_text("{}")  # Just needs to exist

    # Simulate a scan to create the state DB
    subprocess.run([
        sys.executable, "-m", "resonance.cli", "scan", str(library), "--state-db", str(state_db)
    ], check=True)

    # Now run prompt with --cache-db (should not error, should use offline/cached provider)
    result = subprocess.run([
        sys.executable, "-m", "resonance.cli", "prompt", "--state-db", str(state_db), "--cache-db", str(cache_db)
    ], capture_output=True, text=True, check=False)

    # The test is that it runs and does not error (exit code 0 or 1 if prompt needed)
    assert result.returncode in (0, 1)
    # Optionally, check for expected output or error message
    assert "error" not in result.stderr.lower()
