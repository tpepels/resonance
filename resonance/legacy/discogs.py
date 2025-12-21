"""Simplified Discogs client for Resonance.

Provides:
- Discogs API search and release fetching
- Track matching and metadata enrichment
- Integration with cache system
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from mutagen import File as MutagenFile
except ModuleNotFoundError:
    MutagenFile = None

from .musicbrainz import LookupResult
from ..core.heuristics import guess_metadata_from_path
from ..core.models import TrackInfo
from ..infrastructure.cache import MetadataCache
from .. import __version__ as RESONANCE_VERSION

_CACHE_VERSION = "v1"

logger = logging.getLogger(__name__)


class DiscogsClient:
    """Discogs client for Resonance."""

    def __init__(
        self,
        token: str,
        useragent: str = "resonance/0.1",
        cache: Optional[MetadataCache] = None,
        offline: bool = False,
    ) -> None:
        """Initialize the client."""
        if not token:
            raise ValueError("Discogs token required")
        self.token = token
        self.useragent = useragent
        self.cache = cache
        self.offline = offline

    def enrich(self, track: TrackInfo) -> Optional[LookupResult]:
        """Enrich track metadata using Discogs."""
        guess = guess_metadata_from_path(track.path)
        tags = self._read_basic_tags(track.path)

        artist = tags.get("artist") or guess.artist
        title = tags.get("title") or guess.title
        album = tags.get("album") or guess.album
        track_number = guess.track_number
        duration = track.duration_seconds or self._probe_duration(track.path)

        if not (album or title):
            return None

        # Search for release
        release = self._search_release(artist=artist, album=album, title=title)
        if not release:
            return None

        # Fetch full release details
        details = self._fetch_release(release["id"])
        if not details:
            return None

        # Match track within release
        matched_track = self._match_track(
            details.get("tracklist", []),
            title,
            track_number,
            duration,
        )

        # Apply metadata from release
        self._apply_release(track, details, matched_track)
        track.extra.setdefault("discogs_release_id", str(details.get("id")))

        score = 0.35
        track.match_confidence = max(track.match_confidence or 0.0, score)
        return LookupResult(track, score=score)

    def _search_release(self, artist: Optional[str], album: Optional[str], title: Optional[str]) -> Optional[dict]:
        """Search for a release on Discogs."""
        params: Dict[str, str] = {
            "token": self.token,
            "type": "release",
            "per_page": "5",
        }
        if artist:
            params["artist"] = artist
        if album:
            params["release_title"] = album
        if title:
            params["track"] = title

        url = f"https://api.discogs.com/database/search?{urllib.parse.urlencode(params)}"
        data = self._request(url)

        if not data:
            return None

        results = data.get("results", [])
        return results[0] if results else None

    def search_releases(
        self,
        artist: Optional[str],
        album: Optional[str],
        title: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Search Discogs for release candidates."""
        params: Dict[str, str] = {
            "token": self.token,
            "type": "release",
            "per_page": str(limit),
        }
        if artist:
            params["artist"] = artist
        if album:
            params["release_title"] = album
        if title:
            params["track"] = title

        url = f"https://api.discogs.com/database/search?{urllib.parse.urlencode(params)}"
        data = self._request(url)
        if not data:
            return []

        results = data.get("results", [])
        releases: list[dict] = []
        for result in results[:limit]:
            release_id = result.get("id")
            if not release_id:
                continue

            title_val = result.get("title")
            artist_val = result.get("artist")
            parsed_artist, parsed_title = self._split_search_title(title_val)
            if not artist_val:
                artist_val = parsed_artist
            if not result.get("release_title"):
                title_val = parsed_title or title_val

            release = {
                "id": release_id,
                "title": title_val,
                "artist": artist_val,
                "year": result.get("year"),
                "track_count": None,
            }

            details = self._fetch_release(release_id)
            if details:
                release["track_count"] = len(details.get("tracklist", []))
                if not release["title"]:
                    release["title"] = details.get("title")
                if not release["artist"]:
                    release["artist"] = self._join_artists(details.get("artists", []))

            releases.append(release)

        return releases

    def _fetch_release(self, release_id: int) -> Optional[dict]:
        """Fetch full release details from Discogs."""
        # Check cache first
        if self.cache:
            cached = self.cache.get_discogs_release(
                str(release_id),
                cache_version=_CACHE_VERSION,
                client_version=RESONANCE_VERSION,
            )
            if cached:
                logger.debug("Discogs cache hit for release %s", release_id)
                return cached

        url = f"https://api.discogs.com/releases/{release_id}?token={self.token}"
        data = self._request(url)

        if data and self.cache:
            logger.debug("Discogs cache miss; storing release %s", release_id)
            self.cache.set_discogs_release(
                str(release_id),
                data,
                cache_version=_CACHE_VERSION,
                client_version=RESONANCE_VERSION,
            )

        return data

    def get_release(self, release_id: int) -> Optional[dict]:
        """Get release by ID."""
        return self._fetch_release(release_id)

    def _match_track(self, tracklist: List[dict], title: Optional[str], track_number: Optional[int], duration: Optional[int]) -> Optional[dict]:
        """Match a track within release by title, number, or duration."""
        def normalize(value: Optional[str]) -> Optional[str]:
            return value.lower().strip() if isinstance(value, str) else None

        norm_title = normalize(title)

        # Try exact title match first
        if norm_title:
            for track in tracklist:
                if normalize(track.get("title")) == norm_title:
                    return track

        # Try track number match
        if track_number:
            for track in tracklist:
                if self._parse_track_number(track.get("position")) == track_number:
                    return track

        # Try duration match
        if duration:
            for track in tracklist:
                if self._parse_duration(track.get("duration")) == duration:
                    return track

        # Fall back to first track
        return tracklist[0] if tracklist else None

    def _apply_release(self, track: TrackInfo, release: dict, matched_track: Optional[dict]) -> None:
        """Apply release metadata to track."""
        def set_field(attr: str, value: Optional[str]) -> None:
            if value and not getattr(track, attr, None):
                setattr(track, attr, value)

        album_artist = self._join_artists(release.get("artists", []))
        set_field("album", release.get("title"))
        set_field("album_artist", album_artist)

        if matched_track:
            track_artist = self._join_artists(matched_track.get("artists", []))
            set_field("artist", track_artist or album_artist)
        else:
            set_field("artist", album_artist)

        genres = release.get("genres") or release.get("styles") or []
        set_field("genre", genres[0] if genres else None)

    def _join_artists(self, artists: List[dict]) -> Optional[str]:
        """Join artist names from list."""
        names: List[str] = []
        for artist in artists:
            name = artist.get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return self._normalize_artist_string(", ".join(names))

    def _normalize_artist_string(self, value: str) -> Optional[str]:
        """Normalize artist string, removing duplicates and notes."""
        if not value:
            return None

        cleaned = []
        for chunk in re.split(r"[;,]+", value):
            base = chunk.split(" (")[0].strip()
            if base:
                cleaned.append(base)

        # Remove duplicates while preserving order
        unique = []
        for entry in cleaned:
            if entry not in unique:
                unique.append(entry)

        return ", ".join(unique) if unique else None

    @staticmethod
    def _split_search_title(value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """Split search title into artist/title if it uses 'Artist - Title'."""
        if not value or " - " not in value:
            return None, None
        parts = value.split(" - ", 1)
        artist = parts[0].strip() or None
        title = parts[1].strip() or None
        return artist, title

    def _request(self, url: str) -> Optional[dict]:
        """Make HTTP request to Discogs API."""
        if self.offline:
            return None
        req = urllib.request.Request(url, headers={"User-Agent": self.useragent})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            logger.debug("Discogs HTTP error %s for %s: %s", exc.code, url, exc)
        except urllib.error.URLError as exc:
            logger.warning("Discogs request failed for %s: %s", url, exc)
        return None

    def _read_basic_tags(self, path: Path) -> Dict[str, Optional[str]]:
        """Read basic tags from audio file."""
        if MutagenFile is None:
            return {}

        try:
            audio = MutagenFile(path, easy=True)
        except Exception as exc:
            logger.debug("Discogs tag read failed for %s: %s", path, exc)
            return {}

        if not audio or not audio.tags:
            return {}

        return {
            "artist": self._first_tag(audio, ["artist", "albumartist"]),
            "title": self._first_tag(audio, ["title"]),
            "album": self._first_tag(audio, ["album"]),
        }

    @staticmethod
    def _first_tag(audio: Any, keys: List[str]) -> Optional[str]:
        """Get first available tag value."""
        for key in keys:
            values = audio.tags.get(key)
            if values:
                if isinstance(values, list):
                    return values[0]
                return values
        return None

    def _parse_track_number(self, position: Optional[str]) -> Optional[int]:
        """Parse track number from position string (3, 1-3, A1, etc)."""
        if not position:
            return None

        cleaned = position.strip()
        if not cleaned:
            return None

        if cleaned.isdigit():
            return int(cleaned)

        # Handle "disc-track" format (1-3 = track 3)
        match = re.match(r"^\s*\d+\s*[-./]\s*(\d+)\s*$", cleaned)
        if match:
            return int(match.group(1))

        # Handle letter format (A = 1, B = 2)
        match = re.match(r"^\s*([A-Za-z])\s*$", cleaned)
        if match:
            return ord(match.group(1).upper()) - ord("A") + 1

        # Extract first digits
        digits = "".join(ch for ch in cleaned if ch.isdigit())
        return int(digits) if digits else None

    def _parse_duration(self, value: Optional[str]) -> Optional[int]:
        """Parse duration string to seconds."""
        if not value or ":" not in value:
            return None

        try:
            minutes, seconds = value.split(":", 1)
            return int(minutes) * 60 + int(seconds)
        except ValueError:
            return None

    def _probe_duration(self, path: Path) -> Optional[int]:
        """Probe audio file for duration."""
        if MutagenFile is None:
            return None

        try:
            audio = MutagenFile(path)
        except Exception:
            return None

        if not audio or not getattr(audio, "info", None):
            return None

        length = getattr(audio.info, "length", None)
        return int(length) if length else None
