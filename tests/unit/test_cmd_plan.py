"""Unit tests for plan command."""

from __future__ import annotations

from argparse import Namespace

import pytest

from resonance.commands.plan import run_plan
from resonance.errors import ValidationError


class TestRunPlan:
    def test_raises_without_store(self) -> None:
        args = Namespace(dir_id="d-1", json=False)
        with pytest.raises(ValidationError, match="store is required"):
            run_plan(args, store=None)

    def test_raises_for_unknown_dir_id(self, tmp_path) -> None:
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(tmp_path / "state.db")
        args = Namespace(dir_id="nonexistent", json=False)
        try:
            with pytest.raises(ValidationError, match="not found"):
                run_plan(args, store=store)
        finally:
            store.close()

    def test_raises_when_not_pinned(self, tmp_path) -> None:
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(tmp_path / "state.db")
        source = tmp_path / "album"
        source.mkdir()
        try:
            store.get_or_create("d-1", source, "a" * 64)
            args = Namespace(dir_id="d-1", json=False)
            with pytest.raises(ValidationError, match="not pinned"):
                run_plan(args, store=store)
        finally:
            store.close()

    def test_raises_when_provider_client_missing(self, tmp_path) -> None:
        from resonance.core.state import DirectoryState
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(tmp_path / "state.db")
        source = tmp_path / "album"
        source.mkdir()
        try:
            store.get_or_create("d-1", source, "a" * 64)
            store.set_state(
                "d-1",
                DirectoryState.RESOLVED_AUTO,
                pinned_provider="musicbrainz",
                pinned_release_id="mb-123",
            )
            args = Namespace(dir_id="d-1", json=False)
            with pytest.raises(ValidationError, match="provider_client is required"):
                run_plan(args, store=store, provider_client=None)
        finally:
            store.close()
