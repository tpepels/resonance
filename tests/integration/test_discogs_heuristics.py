"""Integration tests for Discogs matching and apply flow."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.enricher import build_tag_patch
from resonance.core.identifier import (
    DirectoryEvidence,
    ProviderRelease,
    ProviderTrack,
    TrackEvidence,
    identify,
)
from resonance.core.identity.signature import dir_signature
from resonance.core.planner import plan_directory
from resonance.core.resolver import resolve_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.release_search import ReleaseSearchService
from resonance.core.models import AlbumInfo, TrackInfo
from resonance.services.tag_writer import MetaJsonTagWriter
from tests.helpers.fs import AudioStubSpec, create_audio_stub


class _StubDiscogsProvider:
    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = list(releases)
        self.search_by_fingerprints_calls = 0
        self.search_by_metadata_calls = 0

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
        data = json.loads(path.with_suffix(path.suffix + ".meta.json").read_text())
        duration = data.get("duration_seconds")
        if isinstance(duration, int):
            total_duration += duration
        tracks.append(
            TrackEvidence(
                fingerprint_id=data.get("fingerprint_id"),
                duration_seconds=duration,
                existing_tags=data.get("tags", {}),
            )
        )
    return DirectoryEvidence(
        tracks=tuple(tracks),
        track_count=len(tracks),
        total_duration_seconds=total_duration,
    )


def test_discogs_singleton_match_plans_and_applies(tmp_path: Path) -> None:
    source_dir = tmp_path / "album"
    specs = [
        AudioStubSpec(
            filename="01 - Track A.flac",
            fingerprint_id="fp-dg-01",
            duration_seconds=180,
            tags={"title": "Track A", "artist": "Discogs Artist", "album": "Discogs Album"},
        ),
        AudioStubSpec(
            filename="02 - Track B.flac",
            fingerprint_id="fp-dg-02",
            duration_seconds=181,
            tags={"title": "Track B", "artist": "Discogs Artist", "album": "Discogs Album"},
        ),
    ]

    source_dir.mkdir(parents=True, exist_ok=True)
    audio_files = [create_audio_stub(source_dir / spec.filename, spec) for spec in specs]

    release = ProviderRelease(
        provider="discogs",
        release_id="dg-1",
        title="Discogs Album",
        artist="Discogs Artist",
        tracks=(
            ProviderTrack(position=1, title="Track A", duration_seconds=180, fingerprint_id="fp-dg-01"),
            ProviderTrack(position=2, title="Track B", duration_seconds=181, fingerprint_id="fp-dg-02"),
        ),
        year=2001,
    )

    provider = _StubDiscogsProvider([release])
    evidence = _evidence_from_files(audio_files)

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        signature_hash = dir_signature(audio_files).signature_hash
        outcome = resolve_directory(
            dir_id="dir-discogs-1",
            path=source_dir,
            signature_hash=signature_hash,
            evidence=evidence,
            store=store,
            provider_client=provider,
        )
        assert outcome.state == DirectoryState.RESOLVED_AUTO
        assert outcome.pinned_provider == "discogs"

        plan = plan_directory(
            dir_id="dir-discogs-1",
            store=store,
            pinned_release=release,
            source_files=audio_files,
        )
        store.set_state(
            plan.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )

        tag_patch = build_tag_patch(
            plan,
            release,
            DirectoryState.RESOLVED_AUTO,
            now_fn=lambda: datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

        output_root = tmp_path / "organized"
        report = apply_plan(
            plan,
            tag_patch,
            store,
            allowed_roots=(output_root,),
            dry_run=False,
            tag_writer=MetaJsonTagWriter(),
        )

        assert report.status == ApplyStatus.APPLIED
        moved = output_root / "Discogs Artist" / "2001 - Discogs Album" / "01 - Track A.flac"
        assert moved.exists()
        tags = MetaJsonTagWriter().read_tags(moved)
        assert tags.get("album") == "Discogs Album"
        assert tags.get("albumartist") == "Discogs Artist"
    finally:
        store.close()


def test_discogs_ambiguous_results_queue_prompt(tmp_path: Path) -> None:
    source_dir = tmp_path / "album"
    specs = [
        AudioStubSpec(
            filename="01 - Track A.flac",
            fingerprint_id="fp-amb-01",
            duration_seconds=180,
            tags={"title": "Track A", "artist": "Artist X", "album": "Ambiguous Album"},
        ),
        AudioStubSpec(
            filename="02 - Track B.flac",
            fingerprint_id="fp-amb-02",
            duration_seconds=181,
            tags={"title": "Track B", "artist": "Artist X", "album": "Ambiguous Album"},
        ),
    ]

    source_dir.mkdir(parents=True, exist_ok=True)
    audio_files = [create_audio_stub(source_dir / spec.filename, spec) for spec in specs]
    signature_hash = dir_signature(audio_files).signature_hash

    release_a = ProviderRelease(
        provider="discogs",
        release_id="dg-a",
        title="Ambiguous Album A",
        artist="Artist X",
        tracks=(
            ProviderTrack(position=1, title="Track A", duration_seconds=180, fingerprint_id="fp-amb-01"),
            ProviderTrack(position=2, title="Track X", duration_seconds=181, fingerprint_id="fp-amb-x"),
        ),
        year=2001,
    )
    release_b = ProviderRelease(
        provider="discogs",
        release_id="dg-b",
        title="Ambiguous Album B",
        artist="Artist X",
        tracks=(
            ProviderTrack(position=1, title="Track B", duration_seconds=180, fingerprint_id="fp-amb-y"),
            ProviderTrack(position=2, title="Track B", duration_seconds=181, fingerprint_id="fp-amb-02"),
        ),
        year=2001,
    )

    provider = _StubDiscogsProvider([release_a, release_b])
    evidence = _evidence_from_files(audio_files)

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        outcome = resolve_directory(
            dir_id="dir-discogs-amb",
            path=source_dir,
            signature_hash=signature_hash,
            evidence=evidence,
            store=store,
            provider_client=provider,
        )
        assert outcome.state == DirectoryState.QUEUED_PROMPT
        assert outcome.needs_prompt is True
    finally:
        store.close()


def test_discogs_compilation_applies_to_various_artists(tmp_path: Path) -> None:
    source_dir = tmp_path / "album"
    specs = [
        AudioStubSpec(
            filename="01 - Track A.flac",
            fingerprint_id="fp-va-01",
            duration_seconds=180,
            tags={"title": "Track A", "artist": "Artist 1", "album": "Hits Vol. 1"},
        ),
        AudioStubSpec(
            filename="02 - Track B.flac",
            fingerprint_id="fp-va-02",
            duration_seconds=181,
            tags={"title": "Track B", "artist": "Artist 2", "album": "Hits Vol. 1"},
        ),
    ]

    source_dir.mkdir(parents=True, exist_ok=True)
    audio_files = [create_audio_stub(source_dir / spec.filename, spec) for spec in specs]
    signature_hash = dir_signature(audio_files).signature_hash

    release = ProviderRelease(
        provider="discogs",
        release_id="dg-va",
        title="Hits Vol. 1",
        artist="Various Artists",
        tracks=(
            ProviderTrack(position=1, title="Track A", duration_seconds=180, fingerprint_id="fp-va-01"),
            ProviderTrack(position=2, title="Track B", duration_seconds=181, fingerprint_id="fp-va-02"),
        ),
        year=1999,
    )

    provider = _StubDiscogsProvider([release])
    evidence = _evidence_from_files(audio_files)

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        outcome = resolve_directory(
            dir_id="dir-discogs-va",
            path=source_dir,
            signature_hash=signature_hash,
            evidence=evidence,
            store=store,
            provider_client=provider,
        )
        assert outcome.state == DirectoryState.RESOLVED_AUTO

        plan = plan_directory(
            dir_id="dir-discogs-va",
            store=store,
            pinned_release=release,
            source_files=audio_files,
        )
        store.set_state(
            plan.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )

        tag_patch = build_tag_patch(
            plan,
            release,
            DirectoryState.RESOLVED_AUTO,
            now_fn=lambda: datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

        output_root = tmp_path / "organized"
        report = apply_plan(
            plan,
            tag_patch,
            store,
            allowed_roots=(output_root,),
            dry_run=False,
            tag_writer=MetaJsonTagWriter(),
        )

        assert report.status == ApplyStatus.APPLIED
        moved = output_root / "Various Artists" / "1999 - Hits Vol. 1" / "01 - Track A.flac"
        assert moved.exists()
    finally:
        store.close()


def test_discogs_duration_tolerance_prefers_closer_release(tmp_path: Path) -> None:
    source_dir = tmp_path / "album"
    specs = [
        AudioStubSpec(
            filename="01 - Track A.flac",
            fingerprint_id="fp-dur-01",
            duration_seconds=180,
            tags={"title": "Track A", "artist": "Artist D", "album": "Duration Album"},
        ),
        AudioStubSpec(
            filename="02 - Track B.flac",
            fingerprint_id="fp-dur-02",
            duration_seconds=200,
            tags={"title": "Track B", "artist": "Artist D", "album": "Duration Album"},
        ),
    ]

    source_dir.mkdir(parents=True, exist_ok=True)
    audio_files = [create_audio_stub(source_dir / spec.filename, spec) for spec in specs]

    evidence = _evidence_from_files(audio_files)

    release_exact = ProviderRelease(
        provider="discogs",
        release_id="dg-dur-exact",
        title="Duration Album",
        artist="Artist D",
        tracks=(
            ProviderTrack(position=1, title="Track A", duration_seconds=180, fingerprint_id="fp-dur-01"),
            ProviderTrack(position=2, title="Track B", duration_seconds=200, fingerprint_id="fp-dur-02"),
        ),
    )
    release_off = ProviderRelease(
        provider="discogs",
        release_id="dg-dur-off",
        title="Duration Album",
        artist="Artist D",
        tracks=(
            ProviderTrack(position=1, title="Track A", duration_seconds=120, fingerprint_id="fp-dur-01"),
            ProviderTrack(position=2, title="Track B", duration_seconds=120, fingerprint_id="fp-dur-02"),
        ),
    )

    provider = _StubDiscogsProvider([release_exact, release_off])
    result = identify(evidence, provider)
    scores = {candidate.release.release_id: candidate.total_score for candidate in result.candidates}
    assert scores["dg-dur-exact"] > scores["dg-dur-off"]


def test_discogs_fuzzy_title_normalization_scores_best_match() -> None:
    album = AlbumInfo(directory=Path("/tmp/album"))
    album.canonical_artist = "Artist / Name"
    album.canonical_album = "Album (Deluxe Edition)"
    album.tracks = [TrackInfo(path=Path("t1.flac")) for _ in range(10)]

    releases = [
        {
            "id": 1,
            "title": "Album - Deluxe Edition",
            "artist": "Artist Name",
            "year": 2001,
            "track_count": 10,
        },
        {
            "id": 2,
            "title": "Other Album",
            "artist": "Different Artist",
            "year": 2002,
            "track_count": 10,
        },
    ]

    class _Discogs:
        def search_releases(self, artist, album, title=None):
            return list(releases)

    svc = ReleaseSearchService(musicbrainz=None, discogs=_Discogs())
    candidates = svc._search_discogs_releases(album)
    assert candidates[0].release_id == "1"
