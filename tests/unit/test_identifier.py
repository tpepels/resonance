"""Unit tests for pure identification logic.

These tests use stub providers to ensure deterministic, fast testing.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Optional

import pytest

from resonance.core.identifier import (
    ConfidenceTier,
    DirectoryEvidence,
    IdentificationResult,
    ProviderRelease,
    ProviderTrack,
    ReleaseScore,
    TrackEvidence,
    calculate_tier,
    identify,
    merge_and_rank_candidates,
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
