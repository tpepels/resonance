"""Integration tests for prompt CLI command wrapper."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from resonance.commands.prompt import run_prompt
from resonance.core.identifier import (
    DirectoryEvidence,
    ProviderRelease,
    ProviderTrack,
    TrackEvidence,
)
from resonance.core.state import DirectoryState
from resonance.errors import ValidationError
from resonance.infrastructure.directory_store import DirectoryStateStore


class StubProviderClient:
    """Stub provider client for testing."""

    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = releases

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        return []

    def search_by_metadata(
        self, artist: str | None, album: str | None, track_count: int
    ) -> list[ProviderRelease]:
        return list(self._releases)


def _write_audio(path: Path, duration: int = 180) -> None:
    """Create a stub audio file with metadata."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub")

    # Create .meta.json sidecar
    meta = {"duration_seconds": duration}
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta))


def test_prompt_cli_wrapper_routes_to_run_prompt_uncertain(tmp_path: Path) -> None:
    """The CLI wrapper should successfully call the underlying prompt function."""
    state_db_path = tmp_path / "state.db"
    store = DirectoryStateStore(state_db_path)
    try:
        # Create a QUEUED_PROMPT directory
        album_dir = tmp_path / "album"
        _write_audio(album_dir / "track.flac", duration=120)

        record = store.get_or_create(
            "dir-1",
            album_dir,
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

        # Create args for CLI
        args = Namespace(state_db=state_db_path)

        # Mock provider with one candidate
        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-1",
            title="Test Album",
            artist="Test Artist",
            tracks=(ProviderTrack(position=1, title="Test Track", duration_seconds=120),),
        )
        provider = StubProviderClient([release])

        # Capture output
        output: list[str] = []

        # Simulate user selecting the first candidate
        def mock_input(_prompt: str) -> str:
            return "1"

        # Run the CLI wrapper
        exit_code = run_prompt(
            args,
            store=store,
            provider_client=provider,
            input_provider=mock_input,
            output_sink=output.append,
        )

        # Should complete successfully
        assert exit_code == 0

        # Should have shown the directory and candidate
        assert any("Queued:" in line for line in output)
        assert any("musicbrainz:mb-1" in line for line in output)

        # Directory should now be RESOLVED_USER
        updated = store.get(record.dir_id)
        assert updated is not None
        assert updated.state == DirectoryState.RESOLVED_USER
        assert updated.pinned_provider == "musicbrainz"
        assert updated.pinned_release_id == "mb-1"
    finally:
        store.close()


def test_prompt_cli_wrapper_requires_store(tmp_path: Path) -> None:
    """CLI wrapper should raise ValidationError if store is None."""
    args = Namespace(state_db=tmp_path / "state.db")

    try:
        run_prompt(args, store=None)
        assert False, "Should have raised ValidationError"
    except ValidationError as exc:
        assert "store is required" in str(exc)


def test_prompt_cli_handles_manual_musicbrainz_id(tmp_path: Path) -> None:
    """User can provide manual MusicBrainz ID via mb:ID syntax."""
    state_db_path = tmp_path / "state.db"
    store = DirectoryStateStore(state_db_path)
    try:
        album_dir = tmp_path / "album"
        _write_audio(album_dir / "track.flac")

        record = store.get_or_create(
            "dir-1",
            album_dir,
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

        args = Namespace(state_db=state_db_path)
        provider = StubProviderClient([])

        output: list[str] = []

        # User provides manual MB ID
        def mock_input(_prompt: str) -> str:
            return "mb:manual-id-123"

        exit_code = run_prompt(
            args,
            store=store,
            provider_client=provider,
            input_provider=mock_input,
            output_sink=output.append,
        )

        assert exit_code == 0

        # Directory should be RESOLVED_USER with manual ID
        updated = store.get(record.dir_id)
        assert updated is not None
        assert updated.state == DirectoryState.RESOLVED_USER
        assert updated.pinned_provider == "musicbrainz"
        assert updated.pinned_release_id == "manual-id-123"
    finally:
        store.close()


def test_prompt_cli_handles_jail_decision(tmp_path: Path) -> None:
    """User can jail a directory via 's' option."""
    state_db_path = tmp_path / "state.db"
    store = DirectoryStateStore(state_db_path)
    try:
        album_dir = tmp_path / "album"
        _write_audio(album_dir / "track.flac")

        record = store.get_or_create(
            "dir-1",
            album_dir,
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

        args = Namespace(state_db=state_db_path)
        provider = StubProviderClient([])

        output: list[str] = []

        # User chooses to jail
        def mock_input(_prompt: str) -> str:
            return "s"

        exit_code = run_prompt(
            args,
            store=store,
            provider_client=provider,
            input_provider=mock_input,
            output_sink=output.append,
        )

        assert exit_code == 0

        # Directory should be JAILED
        updated = store.get(record.dir_id)
        assert updated is not None
        assert updated.state == DirectoryState.JAILED
    finally:
        store.close()


def test_prompt_cli_handles_skip_decision(tmp_path: Path) -> None:
    """User can skip a directory by pressing enter."""
    state_db_path = tmp_path / "state.db"
    store = DirectoryStateStore(state_db_path)
    try:
        album_dir = tmp_path / "album"
        _write_audio(album_dir / "track.flac")

        record = store.get_or_create(
            "dir-1",
            album_dir,
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

        args = Namespace(state_db=state_db_path)
        provider = StubProviderClient([])

        output: list[str] = []

        # User skips by pressing enter
        def mock_input(_prompt: str) -> str:
            return ""

        exit_code = run_prompt(
            args,
            store=store,
            provider_client=provider,
            input_provider=mock_input,
            output_sink=output.append,
        )

        assert exit_code == 0

        # Directory should still be QUEUED_PROMPT
        updated = store.get(record.dir_id)
        assert updated is not None
        assert updated.state == DirectoryState.QUEUED_PROMPT
    finally:
        store.close()
