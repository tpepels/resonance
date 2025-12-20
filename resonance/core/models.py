"""Core data models for Resonance."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class MatchSource(str, Enum):
    """Source of metadata match."""
    MUSICBRAINZ = "musicbrainz"
    DISCOGS = "discogs"
    USER_PROVIDED = "user_provided"
    FINGERPRINT = "fingerprint"
    EXISTING = "existing"


@dataclass(slots=True)
class TrackInfo:
    """Information about a single audio track.

    This is the core data model that flows through all visitors.
    """
    # File information
    path: Path
    duration_seconds: Optional[int] = None

    # Fingerprint data
    fingerprint: Optional[str] = None
    acoustid_id: Optional[str] = None

    # MusicBrainz IDs
    musicbrainz_recording_id: Optional[str] = None
    musicbrainz_release_id: Optional[str] = None

    # Basic metadata
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None

    # Classical music metadata
    composer: Optional[str] = None
    performer: Optional[str] = None
    conductor: Optional[str] = None
    work: Optional[str] = None
    movement: Optional[str] = None

    # Additional metadata
    genre: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    track_total: Optional[int] = None

    # Match metadata
    match_source: Optional[MatchSource] = None
    match_confidence: Optional[float] = None

    # Extra data (for passthrough of unknown tags)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_classical(self) -> bool:
        """Check if this track appears to be classical music.

        True if work is present (even without composer) OR if composer is non-blank.
        False if composer is blank/whitespace-only.
        """
        # Work present means classical, even without composer
        if self.work and self.work.strip():
            return True
        # Composer must be non-blank
        if self.composer and self.composer.strip():
            return True
        return False


@dataclass(slots=True)
class AlbumInfo:
    """Information about an album/release.

    Aggregates information about all tracks in a directory.
    """
    # Source directory
    directory: Path
    source_directory: Optional[Path] = None

    # Canonical identities
    canonical_artist: Optional[str] = None
    canonical_album: Optional[str] = None
    canonical_composer: Optional[str] = None  # For classical music
    canonical_performer: Optional[str] = None  # For classical music

    # Release identifiers
    musicbrainz_release_id: Optional[str] = None
    discogs_release_id: Optional[str] = None

    # Album metadata
    year: Optional[int] = None
    genre: Optional[str] = None
    total_tracks: int = 0

    # Tracks
    tracks: list[TrackInfo] = field(default_factory=list)

    # Match metadata
    match_source: Optional[MatchSource] = None
    match_confidence: Optional[float] = None

    # Processing state
    is_uncertain: bool = False  # Needs user prompt
    is_skipped: bool = False    # User chose to skip (jailed)

    # Extra data for processing (e.g., release candidates)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_classical(self) -> bool:
        """Check if this album appears to be classical music."""
        if not self.tracks:
            return False
        # Consider it classical if majority of tracks are classical
        classical_count = sum(1 for track in self.tracks if track.is_classical)
        return classical_count > len(self.tracks) / 2

    def __post_init__(self) -> None:
        if self.source_directory is None:
            self.source_directory = self.directory

    def _normalize_path_component(self, value: Optional[str]) -> Optional[str]:
        """Normalize a path component by stripping whitespace."""
        if not value:
            return None
        return value.strip() if value.strip() else None

    @property
    def destination_path(self) -> Optional[Path]:
        """Calculate the destination path for this album.

        Returns None if we don't have enough information yet.

        Structure:
        - Classical with single composer: Composer/Album/Performer
        - Classical with multiple composers: Performer/Album
        - Classical compilation: Various Artists/Album
        - Regular music: Artist/Album
        """
        # Normalize all components
        composer = self._normalize_path_component(self.canonical_composer)
        performer = self._normalize_path_component(self.canonical_performer)
        artist = self._normalize_path_component(self.canonical_artist)
        album = self._normalize_path_component(self.canonical_album)

        if self.is_classical:
            # Case 1: Single composer (most classical music)
            if composer:
                if album and performer:
                    # Composer/Work/Performer (e.g., Bach/Goldberg Variations/Glenn Gould)
                    return Path(composer) / album / performer
                elif album:
                    # Composer/Work (no specific performer credited)
                    return Path(composer) / album
                else:
                    # Just composer root (no album means we can't organize further)
                    return Path(composer)

            # Case 2: No single composer (compilations, multi-composer albums)
            else:
                if performer and album:
                    # Performer/Album (e.g., Berlin Philharmonic/Greatest Symphonies)
                    return Path(performer) / album
                elif performer:
                    # Just performer (rare)
                    return Path(performer)
                elif album:
                    # Various Artists/Album (compilation)
                    return Path("Various Artists") / album
                else:
                    # Cannot organize
                    return None
        else:
            # Regular music: Artist/Album
            if artist and album:
                return Path(artist) / album
            else:
                return None


@dataclass(slots=True)
class ArtistInfo:
    """Information about an artist/composer.

    Used for canonical name resolution.
    """
    # All known variants of this artist's name
    name_variants: set[str] = field(default_factory=set)

    # The chosen canonical name
    canonical_name: Optional[str] = None

    # MusicBrainz artist ID (if known)
    musicbrainz_artist_id: Optional[str] = None


class ProcessingError(Exception):
    """Raised when a file cannot be processed but processing should continue."""
    pass


class UserSkippedError(Exception):
    """Raised when user chooses to skip a directory."""
    pass


def parse_int(value: Any) -> Optional[int]:
    """Parse an integer from various input types.

    Handles strings like "3/12" (track number/total) by taking the first part.
    Supports leading/trailing whitespace, plus signs, and negative numbers.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if "/" in cleaned:
            cleaned = cleaned.split("/", 1)[0].strip()
        # Try to parse as integer (handles +/- signs)
        try:
            return int(cleaned)
        except ValueError:
            return None
    try:
        as_str = str(value).strip()
        if as_str.isdigit():
            return int(as_str)
    except Exception:
        pass
    return None
