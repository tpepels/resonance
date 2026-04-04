"""Integration tests for MB ID idempotency on rerun."""

from __future__ import annotations

from pathlib import Path

from resonance.core.identifier import DirectoryEvidence, ProviderCapabilities, TrackEvidence, identify, ProviderRelease, ProviderTrack
from resonance.core.identity.signature import dir_signature
from resonance.core.resolver import resolve_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from tests.helpers.fs import AudioStubSpec, create_audio_stub


class _StubMBProvider:
    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = list(releases)
        self.search_by_fingerprints_calls = 0
        self.search_by_metadata_calls = 0

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=True,
            supports_metadata=True,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        self.search_by_fingerprints_calls += 1
        releases: list[ProviderRelease] = []
        for release in self._releases:
            if any(
                track.fingerprint_id in fingerprints
                for track in release.tracks
                if track.fingerprint_id
            ):
                releases.append(release)
        return releases

    def search_by_metadata(self, artist: str | None, album: str | None, track_count: int) -> list[ProviderRelease]:
        self.search_by_metadata_calls += 1
        return []


def _evidence_from_files(audio_files: list[Path]) -> DirectoryEvidence:
    tracks: list[TrackEvidence] = []
    total_duration = 0
    for path in sorted(audio_files):
        data = path.with_suffix(path.suffix + ".meta.json").read_text()
        meta = __import__("json").loads(data)
        duration = meta.get("duration_seconds")
        if isinstance(duration, int):
            total_duration += duration
        tracks.append(
            TrackEvidence(
                fingerprint_id=meta.get("fingerprint_id"),
                duration_seconds=duration,
                existing_tags=meta.get("tags", {}),
            )
        )
    return DirectoryEvidence(
        tracks=tuple(tracks),
        track_count=len(tracks),
        total_duration_seconds=total_duration,
    )


def test_mb_ids_prevent_rematch_on_rerun(tmp_path: Path) -> None:
    source_dir = tmp_path / "album"
    specs = [
        AudioStubSpec(
            filename="01 - Track A.flac",
            fingerprint_id="fp-mb-01",
            duration_seconds=180,
            tags={"title": "Track A", "album": "Album", "artist": "Artist"},
        ),
        AudioStubSpec(
            filename="02 - Track B.flac",
            fingerprint_id="fp-mb-02",
            duration_seconds=181,
            tags={"title": "Track B", "album": "Album", "artist": "Artist"},
        ),
    ]

    source_dir.mkdir(parents=True, exist_ok=True)
    audio_files = [create_audio_stub(source_dir / spec.filename, spec) for spec in specs]
    signature_hash = dir_signature(audio_files).signature_hash

    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-1",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track A", fingerprint_id="fp-mb-01", recording_id="rec-1"),
            ProviderTrack(position=2, title="Track B", fingerprint_id="fp-mb-02", recording_id="rec-2"),
        ),
    )

    provider = _StubMBProvider([release])
    evidence = _evidence_from_files(audio_files)

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        first = resolve_directory(
            dir_id="dir-mb-id",
            path=source_dir,
            signature_hash=signature_hash,
            evidence=evidence,
            store=store,
            provider_client=provider,
        )
        assert first.state == DirectoryState.RESOLVED_AUTO
        assert provider.search_by_fingerprints_calls == 1

        second = resolve_directory(
            dir_id="dir-mb-id",
            path=source_dir,
            signature_hash=signature_hash,
            evidence=evidence,
            store=store,
            provider_client=provider,
        )
        assert second.state == DirectoryState.RESOLVED_AUTO
        assert provider.search_by_fingerprints_calls == 1
        assert second.pinned_release_id == "mb-1"
    finally:
        store.close()
