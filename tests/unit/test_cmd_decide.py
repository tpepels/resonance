"""Unit tests for decide command."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from resonance.commands.decide import run_decide
from resonance.errors import ValidationError


def _base_args(tmp_path: Path, **overrides) -> Namespace:
    defaults = dict(
        library_root=tmp_path / "library",
        state_db=tmp_path / "state.db",
        cache_db=None,
        offline=False,
        decisions_file=None,
        json=False,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


class TestRunDecide:
    def test_raises_without_store(self, tmp_path: Path) -> None:
        args = _base_args(tmp_path)
        with pytest.raises(ValidationError, match="store is required"):
            run_decide(args, store=None)

    def test_returns_error_for_missing_library_root(self, tmp_path: Path) -> None:
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(tmp_path / "state.db")
        args = _base_args(tmp_path, library_root=tmp_path / "nonexistent")
        try:
            captured: list[str] = []
            code = run_decide(args, store=store, output_sink=captured.append)
            assert code == 3
        finally:
            store.close()

    def test_empty_library_completes_scan_resolve(self, tmp_path: Path) -> None:
        """An empty library directory should scan (0 dirs) and resolve (0 dirs) cleanly."""
        from resonance.infrastructure.directory_store import DirectoryStateStore

        library = tmp_path / "library"
        library.mkdir()

        store = DirectoryStateStore(tmp_path / "state.db")
        args = _base_args(tmp_path, library_root=library)
        try:
            captured: list[str] = []
            code = run_decide(args, store=store, output_sink=captured.append)
            assert code == 0
        finally:
            store.close()

    def test_scan_populates_state_db(self, tmp_path: Path) -> None:
        """Decide should scan directories into the state DB."""
        from resonance.infrastructure.directory_store import DirectoryStateStore
        from tests.helpers.fs import AudioStubSpec, build_album_dir

        library = tmp_path / "library"
        library.mkdir()

        build_album_dir(
            library,
            "Artist - Album",
            [
                AudioStubSpec("01 Track.flac", "fp-1"),
                AudioStubSpec("02 Track.flac", "fp-2"),
            ],
        )

        store = DirectoryStateStore(tmp_path / "state.db")
        args = _base_args(tmp_path, library_root=library)
        try:
            captured: list[str] = []
            code = run_decide(args, store=store, output_sink=captured.append)
            # Scan should succeed even without provider for resolve
            assert code == 0
            # State DB should have the scanned directory
            from resonance.core.state import DirectoryState
            records = store.list_all()
            assert len(records) >= 1
        finally:
            store.close()

    def test_json_output_mode(self, tmp_path: Path) -> None:
        """JSON mode emits structured output."""
        import json
        from resonance.infrastructure.directory_store import DirectoryStateStore

        library = tmp_path / "library"
        library.mkdir()

        store = DirectoryStateStore(tmp_path / "state.db")
        args = _base_args(tmp_path, library_root=library, json=True)
        try:
            captured: list[str] = []
            code = run_decide(args, store=store, output_sink=captured.append)
            assert code == 0
            # JSON output should be parseable
            assert len(captured) == 1
            data = json.loads(captured[0])
            assert data["command"] == "decide"
            assert data["data"]["status"] == "OK"
        finally:
            store.close()
