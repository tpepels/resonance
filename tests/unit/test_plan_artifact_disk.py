"""Unit tests for plan artifact writing to disk (Sprint 2)."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from resonance.commands.plan import run_plan
from resonance.core.identifier import ProviderRelease, ProviderTrack
from resonance.core.state import DirectoryState
from resonance.errors import ValidationError
from resonance.infrastructure.directory_store import DirectoryStateStore


def _make_release() -> ProviderRelease:
    return ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Test Album",
        artist="Test Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1"),
            ProviderTrack(position=2, title="Track 2"),
        ),
    )


def _setup_resolved_dir(store: DirectoryStateStore, dir_id: str, path: Path) -> None:
    store.get_or_create(dir_id, path, "a" * 64)
    store.set_state(
        dir_id,
        DirectoryState.RESOLVED_AUTO,
        pinned_provider="musicbrainz",
        pinned_release_id="mb-123",
        pinned_confidence=0.90,
    )


class TestPlanOutputDir:
    def test_plan_writes_artifact_to_output_dir(self, tmp_path: Path) -> None:
        """When output_dir is given, plan writes <dir_id>.plan.json."""
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            album_dir = tmp_path / "music" / "album"
            album_dir.mkdir(parents=True)
            # Create stub audio files
            for i in range(1, 3):
                stub = album_dir / f"0{i} Track.flac"
                stub.write_bytes(b"\x00" * 100)

            _setup_resolved_dir(store, "dir-plan-1", album_dir)

            args = Namespace(
                dir_id="dir-plan-1",
                state_db=str(tmp_path / "state.db"),
                cache_db=None,
                library_root=str(tmp_path / "music"),
                json=False,
            )
            plan_dir = tmp_path / "plans"
            captured: list[str] = []
            code = run_plan(
                args,
                store=store,
                pinned_release=_make_release(),
                output_sink=captured.append,
                output_dir=plan_dir,
            )
            assert code == 0
            plan_file = plan_dir / "dir-plan-1.plan.json"
            assert plan_file.exists()
            data = json.loads(plan_file.read_text())
            assert data["dir_id"] == "dir-plan-1"
            assert data["provider"] == "musicbrainz"
        finally:
            store.close()

    def test_plan_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        """output_dir is created automatically."""
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            album_dir = tmp_path / "music" / "album"
            album_dir.mkdir(parents=True)
            for i in range(1, 3):
                (album_dir / f"0{i} Track.flac").write_bytes(b"\x00" * 100)

            _setup_resolved_dir(store, "dir-plan-2", album_dir)

            plan_dir = tmp_path / "deep" / "nested" / "plans"
            assert not plan_dir.exists()

            code = run_plan(
                Namespace(
                    dir_id="dir-plan-2",
                    state_db=str(tmp_path / "state.db"),
                    cache_db=None,
                    library_root=str(tmp_path / "music"),
                    json=False,
                ),
                store=store,
                pinned_release=_make_release(),
                output_sink=lambda _: None,
                output_dir=plan_dir,
            )
            assert code == 0
            assert (plan_dir / "dir-plan-2.plan.json").exists()
        finally:
            store.close()

    def test_plan_no_output_dir_skips_write(self, tmp_path: Path) -> None:
        """Without output_dir, no plan file is written (backward compat)."""
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            album_dir = tmp_path / "music" / "album"
            album_dir.mkdir(parents=True)
            for i in range(1, 3):
                (album_dir / f"0{i} Track.flac").write_bytes(b"\x00" * 100)

            _setup_resolved_dir(store, "dir-plan-3", album_dir)

            code = run_plan(
                Namespace(
                    dir_id="dir-plan-3",
                    state_db=str(tmp_path / "state.db"),
                    cache_db=None,
                    library_root=str(tmp_path / "music"),
                    json=False,
                ),
                store=store,
                pinned_release=_make_release(),
                output_sink=lambda _: None,
            )
            assert code == 0
            # No plan files anywhere under tmp_path (except state DB)
            plan_files = list(tmp_path.rglob("*.plan.json"))
            assert plan_files == []
        finally:
            store.close()
