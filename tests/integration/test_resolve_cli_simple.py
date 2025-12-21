"""Simplified integration tests for resolve CLI command."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from resonance.commands.resolve import run_resolve
from resonance.commands.scan import run_scan
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


def _write_audio(path: Path, duration: int = 180, fingerprint: str | None = None) -> None:
    """Create a stub audio file with metadata."""
    import json as json_module

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub")

    # Create .meta.json sidecar with unique metadata
    meta = {"duration_seconds": duration}
    if fingerprint:
        meta["fingerprint_id"] = fingerprint

    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(json_module.dumps(meta))


def test_resolve_processes_new_directories(tmp_path: Path) -> None:
    """Resolve should attempt to process NEW directories."""
    state_db_path = tmp_path / "state.db"
    lib = tmp_path / "library"

    # Create and scan directory
    _write_audio(lib / "album1" / "track.flac", duration=180, fingerprint="fp1")

    store = DirectoryStateStore(state_db_path)
    try:
        # Scan first
        scan_args = Namespace(library_root=lib, state_db=state_db_path, json=False)
        run_scan(scan_args, store=store, output_sink=lambda x: None)

        # Verify directory is in NEW state
        new_dirs = store.list_by_state(DirectoryState.NEW)
        assert len(new_dirs) == 1

        # Resolve (without provider, will fail but command should run)
        resolve_args = Namespace(library_root=lib, state_db=state_db_path, json=False)

        output: list[str] = []
        exit_code = run_resolve(resolve_args, store=store, provider_client=None, output_sink=output.append)

        # Command should complete successfully even if resolution fails
        assert exit_code == 0
        assert any("processed=1" in line for line in output)
    finally:
        store.close()


def test_resolve_json_output_is_valid(tmp_path: Path) -> None:
    """JSON output should be well-formed."""
    state_db_path = tmp_path / "state.db"
    lib = tmp_path / "library"

    # Create and scan directory
    _write_audio(lib / "album1" / "track.flac", duration=180, fingerprint="fp1")

    store = DirectoryStateStore(state_db_path)
    try:
        # Scan first
        scan_args = Namespace(library_root=lib, state_db=state_db_path, json=False)
        run_scan(scan_args, store=store, output_sink=lambda x: None)

        # Resolve with JSON output (no provider, will fail)
        resolve_args = Namespace(library_root=lib, state_db=state_db_path, json=True)

        output: list[str] = []
        exit_code = run_resolve(resolve_args, store=store, provider_client=None, output_sink=output.append)

        assert exit_code == 0
        assert len(output) == 1

        # Parse JSON
        data = json.loads(output[0])
        assert data["schema_version"] == "v1"
        assert data["command"] == "resolve"
        # Without provider, resolution fails, so status is ERROR
        assert data["data"]["status"] in ("OK", "ERROR")
        assert data["data"]["processed"] == 1
        assert len(data["data"]["items"]) == 1
    finally:
        store.close()


def test_resolve_on_nonexistent_path_returns_error(tmp_path: Path) -> None:
    """Resolve should fail gracefully on non-existent library root."""
    state_db_path = tmp_path / "state.db"
    nonexistent = tmp_path / "does_not_exist"

    store = DirectoryStateStore(state_db_path)
    try:
        resolve_args = Namespace(library_root=nonexistent, state_db=state_db_path, json=False)

        output: list[str] = []
        exit_code = run_resolve(resolve_args, store=store, provider_client=None, output_sink=output.append)

        assert exit_code != 0
        assert any("error" in line.lower() for line in output)
    finally:
        store.close()
