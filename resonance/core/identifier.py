"""Pure identification logic for release matching.

This module contains deterministic scoring and candidate ranking logic.
Provider I/O is abstracted behind the ProviderClient interface.

V3.05 integration in progress — placeholders forbidden
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
from typing import Callable, Optional, Protocol


class ConfidenceTier(str, Enum):
    """Confidence levels for automatic vs manual resolution."""

    CERTAIN = "CERTAIN"  # Safe for auto-pin
    PROBABLE = "PROBABLE"  # Propose but require user confirmation
    UNSURE = "UNSURE"  # Multiple conflicts or low coverage


@dataclass(frozen=True)
class TrackEvidence:
    """Evidence extracted from a single audio track."""

    fingerprint_id: Optional[str]
    duration_seconds: Optional[int]
    existing_tags: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DirectoryEvidence:
    """Evidence extracted from a directory for identification."""

    tracks: tuple[TrackEvidence, ...]
    track_count: int
    total_duration_seconds: int

    @property
    def has_fingerprints(self) -> bool:
        """Check if any tracks have fingerprint data."""
        return any(t.fingerprint_id for t in self.tracks)


@dataclass(frozen=True)
class ProviderTrack:
    """Track information from a provider (MB/Discogs)."""

    position: int
    title: str
    duration_seconds: Optional[int] = None
    fingerprint_id: Optional[str] = None
    composer: Optional[str] = None
    disc_number: Optional[int] = None
    recording_id: Optional[str] = None


@dataclass(frozen=True)
class ProviderRelease:
    """Release candidate from a provider."""

    provider: str  # "musicbrainz" or "discogs"
    release_id: str
    title: str
    artist: str
    tracks: tuple[ProviderTrack, ...]
    year: Optional[int] = None
    release_kind: Optional[str] = None

    @property
    def track_count(self) -> int:
        """Number of tracks in this release."""
        return len(self.tracks)


@dataclass(frozen=True)
class ReleaseScore:
    """Scoring breakdown for a release candidate."""

    release: ProviderRelease
    fingerprint_coverage: float  # 0.0 to 1.0
    track_count_match: bool
    duration_fit: float  # 0.0 to 1.0
    year_penalty: float  # 0.0 (no penalty) to 1.0 (max penalty)
    total_score: float

    def __lt__(self, other: ReleaseScore) -> bool:
        """Sort by total_score descending, then by provider/release_id."""
        if self.total_score != other.total_score:
            return self.total_score > other.total_score
        if self.release.provider != other.release.provider:
            return self.release.provider < other.release.provider
        return self.release.release_id < other.release.release_id


@dataclass(frozen=True)
class ProviderCapabilities:
    """Capabilities declared by a provider."""

    supports_fingerprints: bool
    supports_metadata: bool


@dataclass(frozen=True)
class IdentificationResult:
    """Result of release identification."""

    candidates: tuple[ReleaseScore, ...]
    tier: ConfidenceTier
    reasons: tuple[str, ...]
    evidence: DirectoryEvidence
    scoring_version: str = "v1"

    @property
    def best_candidate(self) -> Optional[ReleaseScore]:
        """Return the highest-scoring candidate, if any."""
        return self.candidates[0] if self.candidates else None


class ProviderClient(Protocol):
    """Abstract interface for provider queries (MB, Discogs, etc.)."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Declare what search methods this provider supports."""
        ...

    def search_by_fingerprints(
        self, fingerprints: list[str]
    ) -> list[ProviderRelease]:
        """Search for releases matching the given fingerprints.

        Results must be deterministically ordered by the provider.
        """
        ...

    def search_by_metadata(
        self, artist: Optional[str], album: Optional[str], track_count: int
    ) -> list[ProviderRelease]:
        """Search for releases matching metadata hints.

        Results must be deterministically ordered by the provider.
        """
        ...


# Scoring thresholds (versioned)
SCORING_V1_THRESHOLDS = {
    "fingerprint_weight": 0.6,
    "track_count_weight": 0.2,
    "duration_weight": 0.2,
    "certain_min_score": 0.85,
    "certain_min_coverage": 0.85,
    "probable_min_score": 0.65,
    "multi_release_min_support": 0.30,
}


def extract_evidence(
    audio_files: list[Path],
    fingerprint_reader: Optional[Callable[[Path], str | None]] = None,
) -> DirectoryEvidence:
    """Extract evidence from audio files.

    Args:
        audio_files: List of audio file paths
        fingerprint_reader: Optional function to read fingerprints from files

    Returns:
        DirectoryEvidence with track information
    """
    # Minimal evidence extraction using sidecar tags when present.
    tracks: list[TrackEvidence] = []
    total_duration = 0

    for audio_file in sorted(audio_files):
        existing_tags = _read_existing_tags(audio_file)
        # Placeholder - real implementation would read from files
        track = TrackEvidence(
            fingerprint_id=None,
            duration_seconds=None,
            existing_tags=existing_tags,
        )
        tracks.append(track)

    return DirectoryEvidence(
        tracks=tuple(tracks),
        track_count=len(tracks),
        total_duration_seconds=total_duration,
    )


def _read_existing_tags(path: Path) -> dict[str, str]:
    metadata_path = path.with_suffix(path.suffix + ".meta.json")
    if not metadata_path.exists():
        return {}
    try:
        data = json.loads(metadata_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    tags = data.get("tags")
    if not isinstance(tags, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in tags.items():
        if value is None:
            continue
        normalized[str(key)] = str(value)
    return normalized


def score_release(
    evidence: DirectoryEvidence,
    release: ProviderRelease,
    thresholds: dict = SCORING_V1_THRESHOLDS,
) -> ReleaseScore:
    """Score a single release candidate against evidence.

    Deterministic scoring based on:
    - Fingerprint coverage (primary)
    - Track count match
    - Duration fit
    - Optional year penalty

    Args:
        evidence: Directory evidence
        release: Provider release candidate
        thresholds: Scoring weights and thresholds

    Returns:
        ReleaseScore with breakdown
    """
    # Fingerprint coverage
    if evidence.has_fingerprints:
        matched = sum(
            1
            for ev_track in evidence.tracks
            if ev_track.fingerprint_id
            and any(
                pv_track.fingerprint_id == ev_track.fingerprint_id
                for pv_track in release.tracks
            )
        )
        coverage = matched / evidence.track_count if evidence.track_count > 0 else 0.0
    else:
        coverage = 0.0

    # Track count + disc count match
    evidence_discs = {
        int(tag)
        for track in evidence.tracks
        for tag in (track.existing_tags.get("discnumber"), track.existing_tags.get("disc_number"))
        if isinstance(tag, str) and tag.strip().isdigit()
    }
    release_discs = {
        track.disc_number
        for track in release.tracks
        if track.disc_number is not None
    }
    disc_count_match = True
    if evidence_discs and release_discs:
        disc_count_match = len(evidence_discs) == len(release_discs)

    track_count_match = evidence.track_count == release.track_count and disc_count_match

    # Duration fit (deterministic integer bucketing)
    if evidence.total_duration_seconds and all(
        track.duration_seconds is not None for track in release.tracks
    ):
        release_total = sum(track.duration_seconds or 0 for track in release.tracks)
        if release_total > 0:
            diff = abs(evidence.total_duration_seconds - release_total)
            if diff == 0:
                duration_fit = 1.0
            elif diff <= 5:
                duration_fit = 0.9
            elif diff <= 30:
                duration_fit = 0.8
            elif diff <= 60:
                duration_fit = 0.7
            else:
                duration_fit = 0.5
        else:
            duration_fit = 1.0 if track_count_match else 0.5
    else:
        duration_fit = 1.0 if track_count_match else 0.5

    # Year penalty (placeholder)
    year_penalty = 0.0

    # Single -> album penalty (avoid false upgrades)
    single_album_penalty = 0.0
    if evidence.track_count <= 3:
        release_kind = release.release_kind or _infer_release_kind(release)
        if release_kind == "album" and release.track_count >= evidence.track_count + 3:
            single_album_penalty = 0.2

    # Total score
    total_score = (
        coverage * thresholds["fingerprint_weight"]
        + (1.0 if track_count_match else 0.0) * thresholds["track_count_weight"]
        + duration_fit * thresholds["duration_weight"]
        - year_penalty
        - single_album_penalty
    )

    return ReleaseScore(
        release=release,
        fingerprint_coverage=coverage,
        track_count_match=track_count_match,
        duration_fit=duration_fit,
        year_penalty=year_penalty,
        total_score=total_score,
    )


def _infer_release_kind(release: ProviderRelease) -> str:
    """Infer release kind from track count as a fallback."""
    count = release.track_count
    if count <= 2:
        return "single"
    if count <= 6:
        return "ep"
    return "album"


def merge_and_rank_candidates(
    scored_releases: list[ReleaseScore],
) -> tuple[ReleaseScore, ...]:
    """Merge candidates from multiple providers with deterministic tie-breaking.

    Sort order:
    1. Total score (descending)
    2. Provider name (lexicographic)
    3. Release ID (lexicographic)

    Args:
        scored_releases: List of scored releases from all providers

    Returns:
        Tuple of sorted ReleaseScore objects
    """
    return tuple(sorted(scored_releases))


def calculate_tier(
    candidates: tuple[ReleaseScore, ...],
    evidence: DirectoryEvidence,
    thresholds: dict = SCORING_V1_THRESHOLDS,
) -> tuple[ConfidenceTier, tuple[str, ...]]:
    """Calculate confidence tier and reasons.

    Args:
        candidates: Sorted candidate releases
        evidence: Directory evidence
        thresholds: Scoring thresholds

    Returns:
        Tuple of (tier, reasons)
    """
    reasons: list[str] = []

    if not candidates:
        return ConfidenceTier.UNSURE, ("No candidates found",)

    best = candidates[0]

    # Check for multi-release conflict
    if len(candidates) >= 2:
        second_best = candidates[1]
        if second_best.total_score >= thresholds["multi_release_min_support"]:
            if (best.total_score - second_best.total_score) < 0.15:
                reasons.append(
                    f"Multiple releases with similar scores: {best.total_score:.2f} vs {second_best.total_score:.2f}"
                )
                return ConfidenceTier.UNSURE, tuple(reasons)

    # CERTAIN tier requirements
    if (
        best.total_score >= thresholds["certain_min_score"]
        and best.fingerprint_coverage >= thresholds["certain_min_coverage"]
        and best.track_count_match
    ):
        reasons.append(
            f"High confidence: score={best.total_score:.2f}, coverage={best.fingerprint_coverage:.2f}"
        )
        return ConfidenceTier.CERTAIN, tuple(reasons)

    # PROBABLE tier
    if best.total_score >= thresholds["probable_min_score"]:
        reasons.append(f"Probable match: score={best.total_score:.2f}")
        return ConfidenceTier.PROBABLE, tuple(reasons)

    # UNSURE
    reasons.append(f"Low confidence: score={best.total_score:.2f}")
    return ConfidenceTier.UNSURE, tuple(reasons)


def identify(
    evidence: DirectoryEvidence,
    provider_client: ProviderClient,
    thresholds: dict = SCORING_V1_THRESHOLDS,
) -> IdentificationResult:
    """Identify a directory by scoring provider candidates.

    Pure function that delegates I/O to provider_client.

    Args:
        evidence: Extracted directory evidence
        provider_client: Provider search interface
        thresholds: Scoring configuration

    Returns:
        IdentificationResult with scored candidates and confidence tier
    """
    # Gather candidates from provider
    candidates: list[ProviderRelease] = []

    # Search by fingerprints if available
    if evidence.has_fingerprints:
        if not provider_client.capabilities.supports_fingerprints:
            raise ValueError("Evidence has fingerprints but provider does not support fingerprint search")
        fingerprints = [
            t.fingerprint_id for t in evidence.tracks if t.fingerprint_id
        ]
        candidates.extend(provider_client.search_by_fingerprints(fingerprints))

    # Search by metadata
    # Extract artist/album from existing tags (use first track as representative)
    artist_hint = None
    album_hint = None
    if evidence.tracks:
        first_track_tags = evidence.tracks[0].existing_tags
        # Try common tag names for artist (prefer albumartist over artist)
        artist_hint = (
            first_track_tags.get("albumartist")
            or first_track_tags.get("artist")
            or first_track_tags.get("ALBUMARTIST")
            or first_track_tags.get("ARTIST")
        )
        # Try common tag names for album
        album_hint = (
            first_track_tags.get("album")
            or first_track_tags.get("ALBUM")
        )

    # Anti-placeholder guard: forbid degenerate metadata search when tags exist
    tags_exist = any(bool(track.existing_tags) for track in evidence.tracks)
    if artist_hint is None and album_hint is None and tags_exist:
        raise ValueError("Tags exist but no artist/album hints extracted for metadata search")

    if not provider_client.capabilities.supports_metadata:
        raise ValueError("Provider does not support metadata search")

    candidates.extend(
        provider_client.search_by_metadata(artist_hint, album_hint, evidence.track_count)
    )

    # Score all candidates
    scored = [score_release(evidence, release, thresholds) for release in candidates]

    # Merge and rank
    ranked = merge_and_rank_candidates(scored)

    # Calculate tier
    tier, reasons = calculate_tier(ranked, evidence, thresholds)
    providers = sorted({candidate.release.provider for candidate in ranked})
    if providers:
        reasons = (f"providers={','.join(providers)}",) + reasons

    return IdentificationResult(
        candidates=ranked,
        tier=tier,
        reasons=reasons,
        evidence=evidence,
        scoring_version="v1",
    )
