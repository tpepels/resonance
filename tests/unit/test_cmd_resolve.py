"""Unit tests for resolve command."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from resonance.commands.resolve import run_resolve
from resonance.errors import ValidationError


class TestRunResolve:
    def test_raises_without_store(self, tmp_path: Path) -> None:
        args = Namespace(library_root=str(tmp_path), json=False)
        with pytest.raises(ValidationError, match="store is required"):
            run_resolve(args, store=None)

    def test_nonexistent_library_root_returns_error(self, tmp_path: Path) -> None:
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(tmp_path / "state.db")
        captured: list[str] = []
        args = Namespace(library_root=str(tmp_path / "missing"), json=False)
        try:
            code = run_resolve(args, store=store, output_sink=captured.append)
        finally:
            store.close()
        assert code != 0
        assert any("does not exist" in s for s in captured)

    def test_empty_store_returns_zero(self, tmp_path: Path) -> None:
        from resonance.infrastructure.directory_store import DirectoryStateStore

        lib = tmp_path / "library"
        lib.mkdir()
        store = DirectoryStateStore(tmp_path / "state.db")
        captured: list[str] = []
        args = Namespace(library_root=str(lib), json=False)
        try:
            code = run_resolve(args, store=store, output_sink=captured.append)
        finally:
            store.close()
        assert code == 0
