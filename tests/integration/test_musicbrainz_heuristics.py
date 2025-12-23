"""Integration tests for MusicBrainz matching heuristics."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.enricher import build_tag_patch
from resonance.core.identifier import DirectoryEvidence, ProviderCapabilities, ProviderRelease, ProviderTrack, TrackEvidence, identify
from resonance.core.identity.signature import dir_signature
from resonance.core.planner import plan_directory
from resonance.core.resolver import resolve_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import MetaJsonTagWriter
from tests.helpers.fs import AudioStubSpec, create_audio_stub


class _StubMBProvider:
    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = list(releases)

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=True,
            supports_metadata=True,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
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


def test_musicbrainz_classical_match_plans_and_applies(tmp_path: Path) -> None:
    source_dir = tmp_path / "album"
    specs = [
        AudioStubSpec(
            filename="01 - Mvt I.flac",
            fingerprint_id="fp-mb-01",
            duration_seconds=240,
            tags={"title": "Mvt I", "composer": "Composer A", "album": "Work"},
        ),
        AudioStubSpec(
            filename="02 - Mvt II.flac",
            fingerprint_id="fp-mb-02",
            duration_seconds=241,
            tags={"title": "Mvt II", "composer": "Composer A", "album": "Work"},
        ),
    ]

    source_dir.mkdir(parents=True, exist_ok=True)
    audio_files = [create_audio_stub(source_dir / spec.filename, spec) for spec in specs]
    signature_hash = dir_signature(audio_files).signature_hash

    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-classical-1",
        title="Work",
        artist="Performer A",
        tracks=(
            ProviderTrack(position=1, title="Mvt I", duration_seconds=240, fingerprint_id="fp-mb-01", composer="Composer A"),
            ProviderTrack(position=2, title="Mvt II", duration_seconds=241, fingerprint_id="fp-mb-02", composer="Composer A"),
        ),
        year=1980,
    )

    provider = _StubMBProvider([release])
    evidence = _evidence_from_files(audio_files)

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        outcome = resolve_directory(
            dir_id="dir-mb-1",
            path=source_dir,
            signature_hash=signature_hash,
            evidence=evidence,
            store=store,
            provider_client=provider,
        )
        assert outcome.state == DirectoryState.RESOLVED_AUTO

        record = store.get("dir-mb-1")
        assert record is not None
        plan = plan_directory(
            record=record,
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
        moved = output_root / "Composer A" / "1980 - Work" / "01 - Mvt I.flac"
        assert moved.exists()
    finally:
        store.close()


def test_musicbrainz_multi_disc_match_plans_and_applies(tmp_path: Path) -> None:
    source_dir = tmp_path / "album"
    specs = [
        AudioStubSpec(
            filename="D1-01 - Track A.flac",
            fingerprint_id="fp-md-01",
            duration_seconds=200,
            tags={"title": "Track A", "album": "Multi Disc", "discnumber": "1"},
        ),
        AudioStubSpec(
            filename="D1-02 - Track B.flac",
            fingerprint_id="fp-md-02",
            duration_seconds=201,
            tags={"title": "Track B", "album": "Multi Disc", "discnumber": "1"},
        ),
        AudioStubSpec(
            filename="D2-01 - Track C.flac",
            fingerprint_id="fp-md-03",
            duration_seconds=202,
            tags={"title": "Track C", "album": "Multi Disc", "discnumber": "2"},
        ),
        AudioStubSpec(
            filename="D2-02 - Track D.flac",
            fingerprint_id="fp-md-04",
            duration_seconds=203,
            tags={"title": "Track D", "album": "Multi Disc", "discnumber": "2"},
        ),
    ]

    source_dir.mkdir(parents=True, exist_ok=True)
    audio_files = [create_audio_stub(source_dir / spec.filename, spec) for spec in specs]
    signature_hash = dir_signature(audio_files).signature_hash

    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-multi-disc",
        title="Multi Disc",
        artist="Artist MD",
        tracks=(
            ProviderTrack(position=1, title="Track A", duration_seconds=200, fingerprint_id="fp-md-01", disc_number=1),
            ProviderTrack(position=2, title="Track B", duration_seconds=201, fingerprint_id="fp-md-02", disc_number=1),
            ProviderTrack(position=3, title="Track C", duration_seconds=202, fingerprint_id="fp-md-03", disc_number=2),
            ProviderTrack(position=4, title="Track D", duration_seconds=203, fingerprint_id="fp-md-04", disc_number=2),
        ),
        year=2005,
    )

    provider = _StubMBProvider([release])
    evidence = _evidence_from_files(audio_files)

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        outcome = resolve_directory(
            dir_id="dir-mb-md",
            path=source_dir,
            signature_hash=signature_hash,
            evidence=evidence,
            store=store,
            provider_client=provider,
        )
        assert outcome.state == DirectoryState.RESOLVED_AUTO

        record = store.get("dir-mb-md")
        assert record is not None
        plan = plan_directory(
            record=record,
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
        moved = output_root / "Artist MD" / "2005 - Multi Disc" / "01-01 - Track A.flac"
        assert moved.exists()
    finally:
        store.close()


def test_musicbrainz_prefers_exact_track_count() -> None:
    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id="fp-1", duration_seconds=180),
            TrackEvidence(fingerprint_id="fp-2", duration_seconds=181),
            TrackEvidence(fingerprint_id="fp-3", duration_seconds=182),
        ),
        track_count=3,
        total_duration_seconds=543,
    )

    exact = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-exact",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="A", duration_seconds=180, fingerprint_id="fp-1"),
            ProviderTrack(position=2, title="B", duration_seconds=181, fingerprint_id="fp-2"),
            ProviderTrack(position=3, title="C", duration_seconds=182, fingerprint_id="fp-3"),
        ),
    )
    short = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-short",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="A", duration_seconds=180, fingerprint_id="fp-1"),
            ProviderTrack(position=2, title="B", duration_seconds=181, fingerprint_id="fp-2"),
        ),
    )

    provider = _StubMBProvider([exact, short])
    result = identify(evidence, provider)
    scores = {candidate.release.release_id: candidate.total_score for candidate in result.candidates}
    assert scores["mb-exact"] > scores["mb-short"]


def test_musicbrainz_duration_alignment() -> None:
    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id="fp-a", duration_seconds=180),
            TrackEvidence(fingerprint_id="fp-b", duration_seconds=200),
        ),
        track_count=2,
        total_duration_seconds=380,
    )

    exact = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-dur-exact",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="A", duration_seconds=180, fingerprint_id="fp-a"),
            ProviderTrack(position=2, title="B", duration_seconds=200, fingerprint_id="fp-b"),
        ),
    )
    off = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-dur-off",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="A", duration_seconds=120, fingerprint_id="fp-a"),
            ProviderTrack(position=2, title="B", duration_seconds=120, fingerprint_id="fp-b"),
        ),
    )

    provider = _StubMBProvider([exact, off])
    result = identify(evidence, provider)
    scores = {candidate.release.release_id: candidate.total_score for candidate in result.candidates}
    assert scores["mb-dur-exact"] > scores["mb-dur-off"]


def test_musicbrainz_disc_count_penalty() -> None:
    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(
                fingerprint_id="fp-d1-1",
                duration_seconds=180,
                existing_tags={"discnumber": "1", "artist": "Artist", "album": "Disc Album"},
            ),
            TrackEvidence(
                fingerprint_id="fp-d1-2",
                duration_seconds=181,
                existing_tags={"discnumber": "1", "artist": "Artist", "album": "Disc Album"},
            ),
            TrackEvidence(
                fingerprint_id="fp-d2-1",
                duration_seconds=182,
                existing_tags={"discnumber": "2", "artist": "Artist", "album": "Disc Album"},
            ),
            TrackEvidence(
                fingerprint_id="fp-d2-2",
                duration_seconds=183,
                existing_tags={"discnumber": "2", "artist": "Artist", "album": "Disc Album"},
            ),
        ),
        track_count=4,
        total_duration_seconds=726,
    )

    match = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-disc-match",
        title="Disc Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="A", duration_seconds=180, fingerprint_id="fp-d1-1", disc_number=1),
            ProviderTrack(position=2, title="B", duration_seconds=181, fingerprint_id="fp-d1-2", disc_number=1),
            ProviderTrack(position=3, title="C", duration_seconds=182, fingerprint_id="fp-d2-1", disc_number=2),
            ProviderTrack(position=4, title="D", duration_seconds=183, fingerprint_id="fp-d2-2", disc_number=2),
        ),
    )
    mismatch = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-disc-mismatch",
        title="Disc Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="A", duration_seconds=180, fingerprint_id="fp-d1-1", disc_number=1),
            ProviderTrack(position=2, title="B", duration_seconds=181, fingerprint_id="fp-d1-2", disc_number=1),
            ProviderTrack(position=3, title="C", duration_seconds=182, fingerprint_id="fp-d2-1", disc_number=1),
            ProviderTrack(position=4, title="D", duration_seconds=183, fingerprint_id="fp-d2-2", disc_number=1),
        ),
    )

    provider = _StubMBProvider([match, mismatch])
    result = identify(evidence, provider)
    scores = {candidate.release.release_id: candidate.total_score for candidate in result.candidates}
    assert scores["mb-disc-match"] > scores["mb-disc-mismatch"]
