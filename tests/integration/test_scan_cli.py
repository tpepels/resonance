"""Integration tests for scan CLI command."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from resonance.commands.scan import run_scan
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


def _write_audio(path: Path, content: str = "stub", duration: int = 180, fingerprint: str | None = None) -> None:
    """Create a stub audio file with metadata."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

    # Create .meta.json sidecar with unique metadata
    meta = {"duration_seconds": duration}
    if fingerprint:
        meta["fingerprint_id"] = fingerprint

    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta))


def test_scan_populates_state_db_with_new_directories(tmp_path: Path) -> None:
    """Scan should create NEW directory records in state DB."""
    # Create fresh state DB for this test
    state_db_path = tmp_path / "state.db"

    # Create test library with different metadata to ensure unique dir_ids
    lib = tmp_path / "library"
    _write_audio(lib / "album1" / "track.flac", duration=180, fingerprint="fp1")
    _write_audio(lib / "album2" / "track.mp3", duration=200, fingerprint="fp2")

    args = Namespace(
        library_root=lib,
        state_db=state_db_path,
        json=False,
    )

    # Run scan with a fresh store instance
    store = DirectoryStateStore(state_db_path)
    try:
        output: list[str] = []
        exit_code = run_scan(args, store=store, output_sink=output.append)

        assert exit_code == 0
        assert any("scanned=2" in line for line in output)
        assert any("new=2" in line for line in output)

        # Verify state DB has both records
        records = store.list_by_state(DirectoryState.NEW)
        assert len(records) == 2
        paths = {r.last_seen_path for r in records}
        assert lib / "album1" in paths
        assert lib / "album2" in paths
    finally:
        store.close()


def test_scan_rescan_skips_already_scanned_dirs_with_same_signature(tmp_path: Path) -> None:
    """Rescan should skip directories with unchanged signatures."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        # Create test library
        lib = tmp_path / "library"
        _write_audio(lib / "album1" / "track.flac")

        args = Namespace(
            library_root=lib,
            state_db=tmp_path / "state.db",
            json=False,
        )

        # First scan
        output1: list[str] = []
        exit_code1 = run_scan(args, store=store, output_sink=output1.append)
        assert exit_code1 == 0
        assert any("new=1" in line for line in output1)

        # Second scan (no changes)
        output2: list[str] = []
        exit_code2 = run_scan(args, store=store, output_sink=output2.append)
        assert exit_code2 == 0
        assert any("already_tracked=1" in line for line in output2)
        assert any("new=0" in line for line in output2)
    finally:
        store.close()


def test_scan_json_output_is_deterministic(tmp_path: Path) -> None:
    """JSON output should be deterministic and parseable."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        # Create test library
        lib = tmp_path / "library"
        _write_audio(lib / "album1" / "track.flac")

        args = Namespace(
            library_root=lib,
            state_db=tmp_path / "state.db",
            json=True,
        )

        output: list[str] = []
        exit_code = run_scan(args, store=store, output_sink=output.append)

        assert exit_code == 0
        assert len(output) == 1

        # Parse JSON
        data = json.loads(output[0])
        assert data["schema_version"] == "v1"
        assert data["command"] == "scan"
        assert data["data"]["status"] == "OK"
        assert data["data"]["scanned"] == 1
        assert data["data"]["new"] == 1
        assert len(data["data"]["items"]) == 1

        item = data["data"]["items"][0]
        assert "dir_id" in item
        assert "signature_hash" in item
        assert item["signature_version"] == 1
        assert item["state"] == "NEW"
    finally:
        store.close()


def test_scan_on_nonexistent_path_returns_error_exit_code(tmp_path: Path) -> None:
    """Scan should fail gracefully on non-existent library root."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        nonexistent = tmp_path / "does_not_exist"

        args = Namespace(
            library_root=nonexistent,
            state_db=tmp_path / "state.db",
            json=False,
        )

        output: list[str] = []
        exit_code = run_scan(args, store=store, output_sink=output.append)

        assert exit_code != 0
        assert any("error" in line.lower() for line in output)
    finally:
        store.close()


def test_scan_json_error_on_nonexistent_path(tmp_path: Path) -> None:
    """JSON error output should be well-formed."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        nonexistent = tmp_path / "does_not_exist"

        args = Namespace(
            library_root=nonexistent,
            state_db=tmp_path / "state.db",
            json=True,
        )

        output: list[str] = []
        exit_code = run_scan(args, store=store, output_sink=output.append)

        assert exit_code != 0
        assert len(output) == 1

        data = json.loads(output[0])
        assert data["command"] == "scan"
        assert data["data"]["status"] == "ERROR"
        assert data["data"]["error_type"] == "IOFailure"
        assert "does_not_exist" in data["data"]["error_message"]
    finally:
        store.close()
