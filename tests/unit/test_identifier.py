"""Unit tests for pure identification logic.

These tests use stub providers to ensure deterministic, fast testing.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import pytest

from resonance.core.identifier import (
    ConfidenceTier,
    DirectoryEvidence,
    IdentificationResult,
    ProviderCapabilities,
    ProviderRelease,
    ProviderTrack,
    ReleaseScore,
    TrackEvidence,
    calculate_tier,
    extract_evidence,
    identify,
    merge_and_rank_candidates,
    read_fingerprint_from_test_metadata,
    score_release,
)


def _stable_json_result(result: IdentificationResult) -> str:
    """
    Deterministic JSON serialization for regression testing.

    - Converts Enum values to their .value
    - Converts tuples to lists (json can't serialize tuples)
    - Leaves dataclass structure intact via asdict()
    """
    payload = asdict(result)

    # Normalize Enum to value (asdict() keeps Enum objects)
    payload["tier"] = result.tier.value

    # Ensure scoring_version is present (defensive)
    payload["scoring_version"] = result.scoring_version

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


# Stub provider for testing
class StubProviderClient:
    """Deterministic stub provider for unit tests."""

    def __init__(self, releases: list[ProviderRelease]):
        self.releases = releases

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=True,
            supports_metadata=True,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        return list(self.releases)

    def search_by_metadata(
        self, artist: Optional[str], album: Optional[str], track_count: int
    ) -> list[ProviderRelease]:
        return []


class FlippingOrderProviderClient:
    """
    Returns the same releases but flips order on each call to simulate
    non-deterministic provider ordering.
    """

    def __init__(self, releases: list[ProviderRelease]):
        self._releases = list(releases)
        self._flip = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=True,
            supports_metadata=True,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        self._flip = not self._flip
        if self._flip:
            return list(self._releases)
        return list(reversed(self._releases))

    def search_by_metadata(
        self, artist: Optional[str], album: Optional[str], track_count: int
    ) -> list[ProviderRelease]:
        return []


def test_score_release_perfect_match():
    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id="fp1", duration_seconds=180),
            TrackEvidence(fingerprint_id="fp2", duration_seconds=200),
        ),
        track_count=2,
        total_duration_seconds=380,
    )

    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Test Album",
        artist="Test Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1", fingerprint_id="fp1"),
            ProviderTrack(position=2, title="Track 2", fingerprint_id="fp2"),
        ),
    )

    score = score_release(evidence, release)

    assert score.fingerprint_coverage == 1.0
    assert score.track_count_match is True
    # Keep this assertion broad: scoring weights may evolve, but perfect match should be "high".
    assert score.total_score >= 0.8


def test_score_release_partial_match():
    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id="fp1", duration_seconds=180),
            TrackEvidence(fingerprint_id="fp2", duration_seconds=200),
            TrackEvidence(fingerprint_id="fp3", duration_seconds=220),
        ),
        track_count=3,
        total_duration_seconds=600,
    )

    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Test Album",
        artist="Test Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1", fingerprint_id="fp1"),
            ProviderTrack(position=2, title="Track 2", fingerprint_id="fp2"),
            ProviderTrack(position=3, title="Track 3", fingerprint_id="fp_wrong"),
        ),
    )

    score = score_release(evidence, release)

    assert score.fingerprint_coverage == pytest.approx(2.0 / 3.0)
    assert score.track_count_match is True


def test_score_release_no_fingerprints():
    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id=None, duration_seconds=180),
            TrackEvidence(fingerprint_id=None, duration_seconds=200),
        ),
        track_count=2,
        total_duration_seconds=380,
    )

    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Test Album",
        artist="Test Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1"),
            ProviderTrack(position=2, title="Track 2"),
        ),
    )

    score = score_release(evidence, release)

    assert score.fingerprint_coverage == 0.0
    # Must still be able to produce a non-zero score from track_count/duration components.
    assert score.total_score > 0.0


def test_single_track_penalizes_album_upgrade() -> None:
    evidence = DirectoryEvidence(
        tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
        track_count=1,
        total_duration_seconds=180,
    )
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-album",
        title="Album",
        artist="Artist",
        tracks=tuple(
            ProviderTrack(
                position=index,
                title=f"Track {index}",
                fingerprint_id="fp1" if index == 1 else None,
                duration_seconds=180,
            )
            for index in range(1, 8)
        ),
    )

    score = score_release(evidence, release)
    assert score.total_score < 0.6


def test_merge_and_rank_candidates_deterministic_ordering_tiebreaks_only():
    """
    Tie-break test: keep total_score identical AND component fields identical,
    so ordering depends only on tie-break rules (provider, then release_id).
    """
    release_dg = ProviderRelease(
        provider="discogs",
        release_id="dg-100",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track"),),
    )
    release_mb_200 = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-200",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track"),),
    )
    release_mb_100 = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-100",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track"),),
    )

    # Identical component scores on purpose.
    scores = [
        ReleaseScore(
            release=release_mb_200,
            fingerprint_coverage=0.5,
            track_count_match=True,
            duration_fit=1.0,
            year_penalty=0.0,
            total_score=0.7,
        ),
        ReleaseScore(
            release=release_dg,
            fingerprint_coverage=0.5,
            track_count_match=True,
            duration_fit=1.0,
            year_penalty=0.0,
            total_score=0.7,
        ),
        ReleaseScore(
            release=release_mb_100,
            fingerprint_coverage=0.5,
            track_count_match=True,
            duration_fit=1.0,
            year_penalty=0.0,
            total_score=0.7,
        ),
    ]

    ranked = merge_and_rank_candidates(scores)

    assert ranked[0].release.provider == "discogs"
    assert ranked[1].release.provider == "musicbrainz"
    assert ranked[1].release.release_id == "mb-100"
    assert ranked[2].release.release_id == "mb-200"


def test_calculate_tier_certain():
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1"),
            ProviderTrack(position=2, title="Track 2"),
        ),
    )

    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id="fp1", duration_seconds=180),
            TrackEvidence(fingerprint_id="fp2", duration_seconds=200),
        ),
        track_count=2,
        total_duration_seconds=380,
    )

    score = ReleaseScore(
        release=release,
        fingerprint_coverage=0.95,
        track_count_match=True,
        duration_fit=1.0,
        year_penalty=0.0,
        total_score=0.90,
    )

    tier, reasons = calculate_tier((score,), evidence)

    assert tier == ConfidenceTier.CERTAIN
    assert len(reasons) > 0


def test_calculate_tier_probable():
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1"),
            ProviderTrack(position=2, title="Track 2"),
        ),
    )

    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id="fp1", duration_seconds=180),
            TrackEvidence(fingerprint_id="fp2", duration_seconds=200),
        ),
        track_count=2,
        total_duration_seconds=380,
    )

    score = ReleaseScore(
        release=release,
        fingerprint_coverage=0.70,
        track_count_match=True,
        duration_fit=1.0,
        year_penalty=0.0,
        total_score=0.70,
    )

    tier, _reasons = calculate_tier((score,), evidence)
    assert tier == ConfidenceTier.PROBABLE


def test_calculate_tier_unsure_low_score():
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track 1"),),
    )

    evidence = DirectoryEvidence(
        tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
        track_count=1,
        total_duration_seconds=180,
    )

    score = ReleaseScore(
        release=release,
        fingerprint_coverage=0.30,
        track_count_match=True,
        duration_fit=1.0,
        year_penalty=0.0,
        total_score=0.40,
    )

    tier, _reasons = calculate_tier((score,), evidence)
    assert tier == ConfidenceTier.UNSURE


def test_calculate_tier_certain_at_thresholds() -> None:
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track 1"),),
    )
    evidence = DirectoryEvidence(
        tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
        track_count=1,
        total_duration_seconds=180,
    )
    thresholds = {
        "certain_min_score": 0.80,
        "certain_min_coverage": 0.75,
        "probable_min_score": 0.60,
        "multi_release_min_support": 0.30,
    }
    score = ReleaseScore(
        release=release,
        fingerprint_coverage=0.75,
        track_count_match=True,
        duration_fit=1.0,
        year_penalty=0.0,
        total_score=0.80,
    )

    tier, _reasons = calculate_tier((score,), evidence, thresholds=thresholds)
    assert tier == ConfidenceTier.CERTAIN


def test_calculate_tier_probable_just_below_certain() -> None:
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track 1"),),
    )
    evidence = DirectoryEvidence(
        tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
        track_count=1,
        total_duration_seconds=180,
    )
    thresholds = {
        "certain_min_score": 0.80,
        "certain_min_coverage": 0.75,
        "probable_min_score": 0.60,
        "multi_release_min_support": 0.30,
    }
    score = ReleaseScore(
        release=release,
        fingerprint_coverage=0.75,
        track_count_match=True,
        duration_fit=1.0,
        year_penalty=0.0,
        total_score=0.79,
    )

    tier, _reasons = calculate_tier((score,), evidence, thresholds=thresholds)
    assert tier == ConfidenceTier.PROBABLE


def test_calculate_tier_unsure_multi_release_conflict_uses_stable_prefix():
    """
    Avoid brittle substring matching. We assert a stable prefix that the
    production code currently emits.
    """
    release1 = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track 1"),),
    )

    release2 = ProviderRelease(
        provider="discogs",
        release_id="dg-456",
        title="Album (Remaster)",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track 1"),),
    )

    evidence = DirectoryEvidence(
        tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
        track_count=1,
        total_duration_seconds=180,
    )

    score1 = ReleaseScore(
        release=release1,
        fingerprint_coverage=0.70,
        track_count_match=True,
        duration_fit=1.0,
        year_penalty=0.0,
        total_score=0.72,
    )

    score2 = ReleaseScore(
        release=release2,
        fingerprint_coverage=0.68,
        track_count_match=True,
        duration_fit=1.0,
        year_penalty=0.0,
        total_score=0.70,
    )

    tier, reasons = calculate_tier((score1, score2), evidence)

    assert tier == ConfidenceTier.UNSURE
    assert any(r.startswith("Multiple releases with similar scores:") for r in reasons)


def test_no_fingerprints_can_never_be_certain_regression():
    """
    Regression guard: metadata-only evidence must not produce CERTAIN.
    This protects the Resolver's auto-pin behavior.
    """
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1"),
            ProviderTrack(position=2, title="Track 2"),
        ),
    )

    # No fingerprints at all
    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id=None, duration_seconds=180),
            TrackEvidence(fingerprint_id=None, duration_seconds=200),
        ),
        track_count=2,
        total_duration_seconds=380,
    )

    # Even if a score object is very high, CERTAIN must not be reached because
    # the CERTAIN rule requires fingerprint_coverage >= certain_min_coverage.
    score = ReleaseScore(
        release=release,
        fingerprint_coverage=0.0,
        track_count_match=True,
        duration_fit=1.0,
        year_penalty=0.0,
        total_score=0.99,
    )

    tier, _reasons = calculate_tier((score,), evidence)
    assert tier != ConfidenceTier.CERTAIN


def test_identify_end_to_end_with_stub_provider_json_deterministic():
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Test Album",
        artist="Test Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1", fingerprint_id="fp1"),
            ProviderTrack(position=2, title="Track 2", fingerprint_id="fp2"),
        ),
    )

    provider = StubProviderClient([release])

    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id="fp1", duration_seconds=180),
            TrackEvidence(fingerprint_id="fp2", duration_seconds=200),
        ),
        track_count=2,
        total_duration_seconds=380,
    )

    result1 = identify(evidence, provider)
    result2 = identify(evidence, provider)

    assert result1.tier == ConfidenceTier.CERTAIN
    assert result1.best_candidate is not None
    assert result1.best_candidate.release.release_id == "mb-123"
    assert result1.scoring_version == "v1"

    # Byte-identical determinism check
    assert _stable_json_result(result1) == _stable_json_result(result2)


def test_identify_output_stable_even_if_provider_order_flips_across_calls():
    """
    Provider ordering may be unstable in production. Identifier output should still be stable.
    """
    release1 = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-100",
        title="Album A",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track", fingerprint_id="fp1"),),
    )

    release2 = ProviderRelease(
        provider="discogs",
        release_id="dg-200",
        title="Album B",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track", fingerprint_id="fp1"),),
    )

    provider = FlippingOrderProviderClient([release1, release2])

    evidence = DirectoryEvidence(
        tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
        track_count=1,
        total_duration_seconds=180,
    )

    r1 = identify(evidence, provider)
    r2 = identify(evidence, provider)
    r3 = identify(evidence, provider)

    assert _stable_json_result(r1) == _stable_json_result(r2) == _stable_json_result(r3)


class NoFingerprintProviderClient:
    """Stub provider that does not support fingerprints."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=False,
            supports_metadata=True,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        return []

    def search_by_metadata(
        self, artist: Optional[str], album: Optional[str], track_count: int
    ) -> list[ProviderRelease]:
        return []


class NoMetadataProviderClient:
    """Stub provider that does not support metadata."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=True,
            supports_metadata=False,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        return []

    def search_by_metadata(
        self, artist: Optional[str], album: Optional[str], track_count: int
    ) -> list[ProviderRelease]:
        return []


def test_identify_fingerprint_guard_when_provider_does_not_support():
    """Guard: if evidence has fingerprints but provider does not support them, raise ValueError."""
    provider = NoFingerprintProviderClient()

    evidence = DirectoryEvidence(
        tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
        track_count=1,
        total_duration_seconds=180,
    )

    with pytest.raises(ValueError, match="Evidence has fingerprints but provider does not support fingerprint search"):
        identify(evidence, provider)


def test_identify_metadata_guard_when_provider_does_not_support():
    """Metadata search is optional: if provider does not support metadata, skip it gracefully."""
    provider = NoMetadataProviderClient()

    evidence = DirectoryEvidence(
        tracks=(TrackEvidence(fingerprint_id=None, duration_seconds=180, existing_tags={}),),
        track_count=1,
        total_duration_seconds=180,
    )

    # Should not raise an error - metadata search is optional
    result = identify(evidence, provider)

    # Should result in UNSURE tier with no candidates (no fingerprint or metadata search possible)
    assert result.tier == ConfidenceTier.UNSURE
    assert len(result.candidates) == 0


def test_identify_metadata_guard_when_tags_exist_but_no_hints():
    """Guard: if tags exist but no artist/album hints extracted, raise ValueError for metadata search."""
    provider = StubProviderClient([])

    # Evidence with tags but no artist/album in them
    evidence = DirectoryEvidence(
        tracks=(TrackEvidence(fingerprint_id=None, duration_seconds=180, existing_tags={"genre": "rock"}),),
        track_count=1,
        total_duration_seconds=180,
    )

    with pytest.raises(ValueError, match="Tags exist but no artist/album hints extracted for metadata search"):
        identify(evidence, provider)


def test_extract_evidence_with_fingerprint_reader(tmp_path: Path):
    """Test extract_evidence with fingerprint_reader."""
    from pathlib import Path

    # Create test files
    file1 = tmp_path / "track1.flac"
    file1.write_text("")  # Empty file
    metadata1 = file1.with_suffix(file1.suffix + ".meta.json")
    metadata1.write_text('{"tags": {"duration": 180}, "fingerprint": "fp-123456"}')

    file2 = tmp_path / "track2.flac"
    file2.write_text("")
    metadata2 = file2.with_suffix(file2.suffix + ".meta.json")
    metadata2.write_text('{"tags": {"duration": 200}, "fingerprint": "fp-789012"}')

    audio_files = [file1, file2]
    evidence = extract_evidence(audio_files, fingerprint_reader=read_fingerprint_from_test_metadata)

    assert evidence.track_count == 2
    assert evidence.total_duration_seconds == 380
    assert evidence.has_fingerprints is True
    assert evidence.tracks[0].fingerprint_id == "fp-123456"
    assert evidence.tracks[0].duration_seconds == 180
    assert evidence.tracks[1].fingerprint_id == "fp-789012"
    assert evidence.tracks[1].duration_seconds == 200


def test_extract_evidence_without_fingerprint_reader(tmp_path: Path):
    """Test extract_evidence without fingerprint_reader."""
    from pathlib import Path

    # Create test files
    file1 = tmp_path / "track1.flac"
    file1.write_text("")
    metadata1 = file1.with_suffix(file1.suffix + ".meta.json")
    metadata1.write_text('{"tags": {"duration": 180}}')

    audio_files = [file1]
    evidence = extract_evidence(audio_files)

    assert evidence.track_count == 1
    assert evidence.total_duration_seconds == 180
    assert evidence.has_fingerprints is False
    assert evidence.tracks[0].fingerprint_id is None
    assert evidence.tracks[0].duration_seconds == 180


def test_read_fingerprint_from_test_metadata_success(tmp_path: Path):
    """Test read_fingerprint_from_test_metadata succeeds."""
    file = tmp_path / "track.flac"
    file.write_text("")
    metadata = file.with_suffix(file.suffix + ".meta.json")
    metadata.write_text('{"fingerprint": "fp-test"}')

    result = read_fingerprint_from_test_metadata(file)
    assert result == "fp-test"


def test_read_fingerprint_from_test_metadata_no_file(tmp_path: Path):
    """Test read_fingerprint_from_test_metadata when no metadata file."""
    file = tmp_path / "track.flac"
    file.write_text("")

    result = read_fingerprint_from_test_metadata(file)
    assert result is None


def test_read_fingerprint_from_test_metadata_no_fingerprint(tmp_path: Path):
    """Test read_fingerprint_from_test_metadata when no fingerprint in metadata."""
    file = tmp_path / "track.flac"
    file.write_text("")
    metadata = file.with_suffix(file.suffix + ".meta.json")
    metadata.write_text('{"duration": 180}')

    result = read_fingerprint_from_test_metadata(file)
    assert result is None


def test_identify_uses_fingerprints_when_present():
    """
    Step 4: Wire the fingerprint path *without* AcoustID logic.

    When fingerprints are present and provider supports them:
    - search_by_fingerprints() should be called with non-empty fingerprints
    - fingerprints should be prioritized (flow through the identifier correctly)
    """
    release = ProviderRelease(
        provider="acoustid",
        release_id="ac-123",
        title="Test Album",
        artist="Test Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1", fingerprint_id="fp1"),
            ProviderTrack(position=2, title="Track 2", fingerprint_id="fp2"),
        ),
    )

    # Use a spy provider to track calls
    class FingerprintSpyProviderClient:
        def __init__(self, releases: list[ProviderRelease]):
            self.releases = releases
            self.fingerprint_calls = []
            self.metadata_calls = []

        @property
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(
                supports_fingerprints=True,
                supports_metadata=True,
            )

        def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
            self.fingerprint_calls.append(fingerprints)
            return list(self.releases)

        def search_by_metadata(
            self, artist: Optional[str], album: Optional[str], track_count: int
        ) -> list[ProviderRelease]:
            self.metadata_calls.append((artist, album, track_count))
            return []

    provider = FingerprintSpyProviderClient([release])

    # Evidence with fingerprints present (no metadata tags)
    evidence = DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id="fp1", duration_seconds=180, existing_tags={}),
            TrackEvidence(fingerprint_id="fp2", duration_seconds=200, existing_tags={}),
        ),
        track_count=2,
        total_duration_seconds=380,
    )

    result = identify(evidence, provider)

    # Assertions for Step 4: fingerprints flow through correctly
    assert len(provider.fingerprint_calls) == 1
    assert provider.fingerprint_calls[0] == ["fp1", "fp2"]  # Non-empty fingerprints passed

    # Metadata search also happens (two-channel model), but with None hints since no tags
    assert len(provider.metadata_calls) == 1
    assert provider.metadata_calls[0] == (None, None, 2)  # No artist/album hints extracted

    # Should produce a CERTAIN result since fingerprint coverage is perfect
    assert isinstance(result, IdentificationResult)
    assert result.tier == ConfidenceTier.CERTAIN
    assert result.evidence == evidence
    assert len(result.candidates) == 1  # Only one candidate from fingerprint search
