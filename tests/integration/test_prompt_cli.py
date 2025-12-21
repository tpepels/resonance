"""Integration tests for prompt CLI ergonomics."""

from __future__ import annotations

from pathlib import Path

from resonance.commands.prompt import run_prompt_uncertain
from resonance.core.identifier import (
    DirectoryEvidence,
    ProviderRelease,
    ProviderTrack,
    TrackEvidence,
)
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


class StubProviderClient:
    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = releases

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        return []

    def search_by_metadata(
        self, artist: str | None, album: str | None, track_count: int
    ) -> list[ProviderRelease]:
        return list(self._releases)


def _write_audio(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub")


def test_prompt_outputs_tracks_and_candidates_with_scores(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        album_dir = tmp_path / "album"
        _write_audio(album_dir / "01 - Track A.flac")
        _write_audio(album_dir / "02 - Track B.flac")

        record = store.get_or_create("dir-1", album_dir, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-1",
            title="Album",
            artist="Artist",
            tracks=(
                ProviderTrack(position=1, title="Track A", duration_seconds=120),
                ProviderTrack(position=2, title="Track B", duration_seconds=240),
            ),
        )
        provider = StubProviderClient([release])

        def evidence_builder(_files: list[Path]) -> DirectoryEvidence:
            tracks = (
                TrackEvidence(fingerprint_id=None, duration_seconds=120, existing_tags={}),
                TrackEvidence(fingerprint_id=None, duration_seconds=240, existing_tags={}),
            )
            return DirectoryEvidence(
                tracks=tracks,
                track_count=2,
                total_duration_seconds=360,
            )

        output: list[str] = []

        def sink(line: str) -> None:
            output.append(line)

        run_prompt_uncertain(
            store=store,
            provider_client=provider,
            input_provider=lambda _prompt: "s",
            output_sink=sink,
            evidence_builder=evidence_builder,
        )

        assert "Tracks:" in output
        assert "  1. 01 - Track A.flac (120s)" in output
        assert "  2. 02 - Track B.flac (240s)" in output
        assert "[1] musicbrainz:mb-1 Artist - Album score=" in "\n".join(output)
        assert any(line.startswith("Reasons:") for line in output)
    finally:
        store.close()


def test_prompt_supports_jail_decision(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        album_dir = tmp_path / "album"
        _write_audio(album_dir / "01 - Track A.flac")
        record = store.get_or_create("dir-1", album_dir, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

        provider = StubProviderClient([])

        def evidence_builder(_files: list[Path]) -> DirectoryEvidence:
            tracks = (
                TrackEvidence(fingerprint_id=None, duration_seconds=100, existing_tags={}),
            )
            return DirectoryEvidence(
                tracks=tracks,
                track_count=1,
                total_duration_seconds=100,
            )

        output: list[str] = []

        def sink(line: str) -> None:
            output.append(line)

        run_prompt_uncertain(
            store=store,
            provider_client=provider,
            input_provider=lambda _prompt: "s",
            output_sink=sink,
            evidence_builder=evidence_builder,
        )

        updated = store.get(record.dir_id)
        assert updated is not None
        assert updated.state == DirectoryState.JAILED
        assert any("Jail this directory" in line for line in output)
    finally:
        store.close()


def test_prompt_orders_candidates_and_options_stably(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        album_dir = tmp_path / "album"
        _write_audio(album_dir / "02 - Track B.flac")
        _write_audio(album_dir / "01 - Track A.flac")

        record = store.get_or_create("dir-1", album_dir, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

        releases = [
            ProviderRelease(
                provider="musicbrainz",
                release_id="mb-2",
                title="Album",
                artist="Artist",
                tracks=(
                    ProviderTrack(position=1, title="Track A", duration_seconds=100),
                    ProviderTrack(position=2, title="Track B", duration_seconds=100),
                ),
            ),
            ProviderRelease(
                provider="discogs",
                release_id="dg-1",
                title="Album",
                artist="Artist",
                tracks=(
                    ProviderTrack(position=1, title="Track A", duration_seconds=100),
                    ProviderTrack(position=2, title="Track B", duration_seconds=100),
                ),
            ),
        ]
        provider = StubProviderClient(releases)

        def evidence_builder(_files: list[Path]) -> DirectoryEvidence:
            tracks = (
                TrackEvidence(fingerprint_id=None, duration_seconds=100, existing_tags={}),
                TrackEvidence(fingerprint_id=None, duration_seconds=100, existing_tags={}),
            )
            return DirectoryEvidence(
                tracks=tracks,
                track_count=2,
                total_duration_seconds=200,
            )

        output: list[str] = []

        def sink(line: str) -> None:
            output.append(line)

        run_prompt_uncertain(
            store=store,
            provider_client=provider,
            input_provider=lambda _prompt: "",
            output_sink=sink,
            evidence_builder=evidence_builder,
        )

        candidate_lines = [line for line in output if line.startswith("[")]
        assert candidate_lines == [
            "[1] discogs:dg-1 Artist - Album score=0.40 coverage=0.00",
            "[2] musicbrainz:mb-2 Artist - Album score=0.40 coverage=0.00",
        ]

        options_block = output[output.index("Options:") :]
        assert options_block[:6] == [
            "Options:",
            "  [1..N] Select a release from the list",
            "  [mb:ID] Provide MusicBrainz release ID",
            "  [dg:ID] Provide Discogs release ID",
            "  [s] Jail this directory",
            "  [enter] Skip for now",
        ]
    finally:
        store.close()
