"""Release search and scoring service.

Searches both MusicBrainz and Discogs for release candidates and scores them
based on track count, duration matches, and fingerprint matches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
import re
from typing import Optional

from .models import AlbumInfo
from .musicbrainz import MusicBrainzClient
from .discogs import DiscogsClient

logger = logging.getLogger(__name__)


@dataclass
class ReleaseCandidate:
    """A candidate release with score."""
    provider: str  # "musicbrainz" or "discogs"
    release_id: str
    title: str
    artist: str
    year: Optional[int]
    track_count: int
    score: float
    coverage: float  # Percentage of tracks matched (0.0-1.0)

    def __repr__(self) -> str:
        return f"{self.provider}:{self.release_id} ({self.score:.2f})"


class ReleaseSearchService:
    """Search and score release candidates from MusicBrainz and Discogs."""

    def __init__(
        self,
        musicbrainz: MusicBrainzClient,
        discogs: Optional[DiscogsClient] = None,
    ):
        self.musicbrainz = musicbrainz
        self.discogs = discogs

    def search_releases(self, album: AlbumInfo) -> list[ReleaseCandidate]:
        """Search for release candidates and return ranked list.

        Args:
            album: Album with tracks (fingerprinted)

        Returns:
            List of ReleaseCandidate sorted by score (best first)
        """
        candidates: list[ReleaseCandidate] = []

        # Collect release IDs from fingerprinted tracks
        mb_release_ids = self._collect_musicbrainz_releases(album)

        # Search MusicBrainz releases
        for release_id in mb_release_ids:
            candidate = self._score_musicbrainz_release(release_id, album)
            if candidate:
                candidates.append(candidate)

        # Search Discogs if available
        if self.discogs:
            dg_candidates = self._search_discogs_releases(album)
            candidates.extend(dg_candidates)

        # Sort by score (descending)
        candidates.sort(key=lambda c: c.score, reverse=True)

        # Return top 10
        return candidates[:10]

    def _collect_musicbrainz_releases(self, album: AlbumInfo) -> set[str]:
        """Collect MusicBrainz release IDs from fingerprinted tracks."""
        release_ids = set()

        for track in album.tracks:
            if track.musicbrainz_release_id:
                release_ids.add(track.musicbrainz_release_id)

        return release_ids

    def _score_musicbrainz_release(
        self,
        release_id: str,
        album: AlbumInfo,
    ) -> Optional[ReleaseCandidate]:
        """Score a MusicBrainz release against the album.

        Args:
            release_id: MusicBrainz release ID
            album: Album to match

        Returns:
            ReleaseCandidate or None if fetching failed
        """
        # Fetch release from MusicBrainz (with caching)
        release_data = self.musicbrainz._fetch_release_tracks(release_id)
        if not release_data:
            return None

        # Extract release info
        title = release_data.album_title or "Unknown"
        artist = release_data.album_artist or "Unknown"
        year = self._parse_year(release_data.release_date)
        track_count = len(release_data.tracks)

        # Calculate score
        score = 0.0
        matched_tracks = 0

        # Base score from fingerprint matches
        for track in album.tracks:
            if track.musicbrainz_release_id == release_id:
                score += 0.5
                matched_tracks += 1

        # Track count bonus
        if track_count > 0:
            ratio = min(len(album.tracks), track_count) / max(len(album.tracks), track_count)
            if ratio >= 0.95:
                score += 0.15
            elif ratio >= 0.85:
                score += 0.10
            elif ratio >= 0.70:
                score += 0.05
            elif ratio <= 0.40:
                score -= 0.15

        # Year bonus (if we have year info)
        if album.year and year:
            diff = abs(album.year - year)
            if diff == 0:
                score += 0.05
            elif diff == 1:
                score += 0.02
            elif diff >= 3:
                score -= 0.05

        # Coverage (percentage of tracks matched)
        coverage = matched_tracks / len(album.tracks) if album.tracks else 0.0

        # Penalize if coverage is too low
        if coverage < 0.5:
            score -= 0.20
        elif coverage < 0.7:
            score -= 0.10

        return ReleaseCandidate(
            provider="musicbrainz",
            release_id=release_id,
            title=title,
            artist=artist,
            year=year,
            track_count=track_count,
            score=max(0.0, score),  # Don't go negative
            coverage=coverage,
        )

    def _search_discogs_releases(self, album: AlbumInfo) -> list[ReleaseCandidate]:
        """Search Discogs for release candidates.

        Args:
            album: Album to search

        Returns:
            List of ReleaseCandidate from Discogs
        """
        if not self.discogs:
            return []

        candidates: list[ReleaseCandidate] = []

        # Build search query from album info
        artist = album.canonical_artist or album.canonical_composer
        album_title = album.canonical_album

        if not artist and not album_title:
            # Need at least artist or album
            return []

        releases = self.discogs.search_releases(
            artist=artist,
            album=album_title,
        )
        if not releases:
            return candidates

        for release in releases:
            release_id = str(release.get("id"))
            title = release.get("title") or "Unknown"
            release_artist = release.get("artist") or "Unknown"
            year = release.get("year")
            track_count = int(release.get("track_count") or 0)

            score = 0.0
            if artist and release_artist and self._normalize(artist) == self._normalize(release_artist):
                score += 0.2
            if album_title and title and self._normalize(album_title) == self._normalize(title):
                score += 0.2

            coverage = 0.0
            if album.tracks and track_count:
                ratio = min(len(album.tracks), track_count) / max(len(album.tracks), track_count)
                coverage = ratio
                if ratio >= 0.95:
                    score += 0.15
                elif ratio >= 0.85:
                    score += 0.10
                elif ratio >= 0.70:
                    score += 0.05
                elif ratio <= 0.40:
                    score -= 0.15

            candidates.append(
                ReleaseCandidate(
                    provider="discogs",
                    release_id=release_id,
                    title=title,
                    artist=release_artist,
                    year=year,
                    track_count=track_count,
                    score=max(0.0, score),
                    coverage=coverage,
                )
            )

        return candidates

    def _parse_year(self, date_str: Optional[str]) -> Optional[int]:
        """Parse year from date string (YYYY-MM-DD or YYYY)."""
        if not date_str:
            return None

        try:
            # Try to extract first 4 digits
            year_str = date_str.split('-')[0]
            if year_str.isdigit() and len(year_str) == 4:
                return int(year_str)
        except Exception:
            pass

        return None

    @staticmethod
    def _normalize(value: str) -> str:
        cleaned = value.casefold()
        cleaned = re.sub(r"[^\w\s]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def auto_select_best(
        self,
        candidates: list[ReleaseCandidate],
        min_score: float = 0.8,
        min_coverage: float = 0.8,
    ) -> Optional[ReleaseCandidate]:
        """Auto-select best candidate if confidence is high enough.

        Args:
            candidates: List of candidates (sorted by score)
            min_score: Minimum score required for auto-selection
            min_coverage: Minimum coverage required

        Returns:
            Best candidate if it meets thresholds, None otherwise
        """
        if not candidates:
            return None

        for candidate in candidates:
            if not isinstance(candidate.score, (int, float)):
                raise TypeError("Candidate score must be numeric")
            if not isinstance(candidate.coverage, (int, float)):
                raise TypeError("Candidate coverage must be numeric")

        candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
        best = candidates[0]

        # Check if best candidate meets thresholds
        if best.score >= min_score and best.coverage >= min_coverage:
            # Check if it's significantly better than second best
            if len(candidates) > 1:
                second = candidates[1]
                # Require at least 0.15 point lead
                if best.score - second.score < 0.15:
                    return None

            return best

        return None
