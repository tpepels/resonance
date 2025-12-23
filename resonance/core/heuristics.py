"""Heuristics for guessing metadata from file paths.

Used as a fallback when fingerprinting fails or for initial matching hints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2212"
TRACK_PATTERN = re.compile(rf"^(?P<num>\d{{1,3}})(?:[\s._\-{_DASH_CHARS}]+)(?P<title>.+)$")
ARTIST_ALBUM_PATTERN = re.compile(r"^(?P<artist>[^/]+?)\s*[-–]\s*(?P<album>.+)$")


@dataclass(slots=True)
class PathGuess:
    """Metadata guessed from file path structure."""

    artist: Optional[str] = None
    album: Optional[str] = None
    title: Optional[str] = None
    track_number: Optional[int] = None

    def confidence(self) -> float:
        """Calculate confidence score (0.0-1.0) based on how much we guessed."""
        score = 0.0
        if self.artist:
            score += 0.25
        if self.album:
            score += 0.25
        if self.title:
            score += 0.25
        if self.track_number is not None:
            score += 0.25
        return score


def guess_metadata_from_path(path: Path) -> PathGuess:
    """Extract metadata hints from file path.

    Examples:
        /Music/The Beatles/Abbey Road/01 Come Together.mp3
        -> artist: The Beatles, album: Abbey Road, track: 1, title: Come Together

        /Music/Classical/Bach - Goldberg Variations/01 Aria.flac
        -> artist: Bach, album: Goldberg Variations, track: 1, title: Aria

    Args:
        path: Path to audio file

    Returns:
        PathGuess with extracted metadata
    """
    guess = PathGuess()

    # Extract from filename
    filename = path.stem
    track_match = TRACK_PATTERN.match(filename)

    if track_match:
        guess.track_number = int(track_match.group("num"))
        guess.title = _clean(track_match.group("title"))
    else:
        guess.title = _clean(filename)

    # Extract from directory structure
    parent_parts = path.parts[:-1]
    if not parent_parts:
        return guess

    album_dir = parent_parts[-1]
    artist_dir = parent_parts[-2] if len(parent_parts) >= 2 else None

    # Try to parse "Artist - Album" pattern in directory name
    match = ARTIST_ALBUM_PATTERN.match(album_dir)
    if match:
        guess.artist = _clean(match.group("artist"))
        guess.album = _clean(match.group("album"))
    else:
        guess.album = _clean(album_dir)
        if artist_dir:
            guess.artist = _clean(artist_dir)

    return guess


def _clean(value: str | None) -> Optional[str]:
    """Clean up extracted values."""
    if not value:
        return None
    cleaned = value.replace("_", " ").strip(" ._-")
    return cleaned or None
