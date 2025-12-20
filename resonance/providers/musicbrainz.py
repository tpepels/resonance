"""Simplified MusicBrainz client for Resonance.

Provides:
- AcoustID fingerprinting
- MusicBrainz API integration
- Release lookups and track matching
- Metadata enrichment
"""

from __future__ import annotations

import difflib
import logging
import re
import socket
import time
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

try:
    import acoustid
except ModuleNotFoundError:
    acoustid = None

try:
    import musicbrainzngs
except ModuleNotFoundError:
    musicbrainzngs = None

try:
    from mutagen import File as MutagenFile
except ModuleNotFoundError:
    MutagenFile = None

from ..core.heuristics import PathGuess, guess_metadata_from_path
from ..core.models import TrackInfo
from ..infrastructure.cache import MetadataCache

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LookupResult:
    """Result from a MusicBrainz track lookup."""
    track: TrackInfo
    score: float


@dataclass(slots=True)
class ReleaseTrack:
    """Track within a release."""
    recording_id: str
    disc_number: Optional[int]
    number: Optional[int]
    title: Optional[str]
    duration_seconds: Optional[int]


class ReleaseData:
    """MusicBrainz release with track listing."""

    def __init__(
        self,
        release_id: str,
        album_title: Optional[str],
        album_artist: Optional[str],
        release_date: Optional[str],
    ) -> None:
        self.release_id = release_id
        self.album_title = album_title
        self.album_artist = album_artist
        self.release_date = release_date
        self.disc_count = 0
        self.formats: List[str] = []
        self.tracks: List[ReleaseTrack] = []
        self.claimed: set[str] = set()

    def add_track(self, track: ReleaseTrack) -> None:
        """Add a track to the release."""
        self.tracks.append(track)

    def mark_claimed(self, recording_id: Optional[str]) -> None:
        """Mark a recording as already matched."""
        if recording_id:
            self.claimed.add(recording_id)

    def claim(
        self, guess: PathGuess, duration: Optional[int]
    ) -> Optional[Tuple[ReleaseTrack, float]]:
        """Match a file to a track in this release."""
        # Try exact track number match
        if guess.track_number:
            for track in self.tracks:
                if track.recording_id not in self.claimed and track.number == guess.track_number:
                    self.claimed.add(track.recording_id)
                    return track, 0.75

        # Try fuzzy title match
        result = self._fuzzy_title_match(guess, duration)
        if result:
            track, confidence = result
            self.claimed.add(track.recording_id)
            return track, confidence
        return None

    def _fuzzy_title_match(
        self, guess: PathGuess, duration: Optional[int]
    ) -> Optional[Tuple[ReleaseTrack, float]]:
        """Match by fuzzy title comparison."""
        if not guess.title:
            return None
        normalized_guess = _normalize_title(guess.title)
        if not normalized_guess:
            return None

        best_track = None
        best_score = 0.0

        for track in self.tracks:
            if track.recording_id in self.claimed or not track.title:
                continue
            normalized_track = _normalize_title(track.title)
            if not normalized_track:
                continue

            ratio = difflib.SequenceMatcher(None, normalized_guess, normalized_track).ratio()

            # Reject if duration is way off
            if duration and track.duration_seconds:
                if abs(track.duration_seconds - duration) > max(15, int(0.25 * track.duration_seconds)):
                    continue

            if ratio > best_score:
                best_track = track
                best_score = ratio

        if best_track and best_score >= 0.55:
            return best_track, min(0.85, 0.45 + (best_score - 0.55) * 0.4)
        return None


@dataclass(slots=True)
class ReleaseMatch:
    """Matched track within a release."""
    release: ReleaseData
    track: ReleaseTrack
    confidence: float


class ReleaseTracker:
    """Tracks releases per directory for batch matching."""

    def __init__(self) -> None:
        self.dir_release: Dict[Path, tuple[str, float]] = {}
        self.releases: Dict[str, ReleaseData] = {}

    def register(
        self,
        album_dir: Path,
        release_id: Optional[str],
        fetch_release: Callable[[str], Optional[ReleaseData]],
        matched_recording_id: Optional[str] = None,
    ) -> None:
        """Register a release for a directory."""
        if not release_id:
            return
        if album_dir not in self.dir_release:
            self.dir_release[album_dir] = (release_id, 0.0)
        if release_id not in self.releases:
            release = fetch_release(release_id)
            if release:
                self.releases[release_id] = release
        if matched_recording_id:
            self.releases[release_id].mark_claimed(matched_recording_id)

    def match(
        self, album_dir: Path, guess: PathGuess, duration: Optional[int]
    ) -> Optional[ReleaseMatch]:
        """Try to match a track against the release for this directory."""
        entry = self.dir_release.get(album_dir)
        if not entry:
            return None
        release = self.releases.get(entry[0])
        if not release:
            return None
        claimed = release.claim(guess, duration)
        if claimed:
            track, confidence = claimed
            return ReleaseMatch(release=release, track=track, confidence=confidence)
        return None

    def remember_release(
        self, album_dir: Path, release_id: Optional[str], score: float
    ) -> None:
        """Remember the best release for a directory."""
        if not release_id:
            return
        current = self.dir_release.get(album_dir)
        if current and current[1] >= score:
            return
        self.dir_release[album_dir] = (release_id, score)


class MusicBrainzClient:
    """Simplified MusicBrainz client for Resonance."""

    def __init__(
        self,
        acoustid_api_key: str,
        useragent: str = "resonance/0.1",
        cache: Optional[MetadataCache] = None,
        network_retries: int = 1,
        retry_backoff: float = 0.5,
    ) -> None:
        """Initialize the client.

        Args:
            acoustid_api_key: API key for AcoustID
            useragent: User agent string for MusicBrainz
            cache: Optional cache instance
            network_retries: Number of retries for network errors
            retry_backoff: Backoff multiplier for retries
        """
        self.acoustid_api_key = acoustid_api_key
        self.cache = cache
        self.network_retries = network_retries
        self.retry_backoff = retry_backoff
        self.release_tracker = ReleaseTracker()
        self._network_disabled_until: float = 0.0
        self._last_network_warning: float = 0.0

        if musicbrainzngs is not None:
            musicbrainzngs.set_useragent("resonance", "0.1", contact=useragent)

    def enrich(self, track: TrackInfo) -> Optional[LookupResult]:
        """Enrich track metadata using MusicBrainz.

        Args:
            track: Track to enrich

        Returns:
            LookupResult if successful, None otherwise
        """
        if self._network_disabled_until and time.time() < self._network_disabled_until:
            return None

        guess = guess_metadata_from_path(track.path)
        album_dir = track.path.parent

        # Get directory context
        dir_release = self.release_tracker.dir_release.get(album_dir)
        dir_release_id = dir_release[0] if dir_release else None

        # Try fingerprinting
        duration, fingerprint = self._fingerprint(track.path)
        if duration:
            track.duration_seconds = duration
        else:
            track.duration_seconds = track.duration_seconds or self._probe_duration(track.path)

        # Try fingerprinting
        if fingerprint and duration:
            track.fingerprint = fingerprint
            result = self._lookup_by_fingerprint(track, duration, fingerprint, dir_release_id)
            if result:
                self._after_match(track)
                return result

        # Try existing tags
        tags = self._read_basic_tags(track.path)
        if tags and tags.get("artist") and tags.get("title"):
            result = self._lookup_by_metadata(track, tags, dir_release_id)
            if result:
                self._after_match(track)
                return result

        # Try filename guess
        if guess.confidence() >= 0.4 and guess.title:
            result = self._lookup_by_guess(track, guess, dir_release_id)
            if result:
                self._after_match(track)
                return result

        # Try release matching
        release_match = self.release_tracker.match(album_dir, guess, track.duration_seconds)
        if release_match:
            return self._apply_release_match(track, release_match)

        return None

    def _fingerprint(self, path: Path) -> tuple[Optional[int], Optional[str]]:
        """Generate AcoustID fingerprint."""
        if acoustid is None:
            return None, None
        try:
            duration, fingerprint = acoustid.fingerprint_file(str(path))
            return duration, fingerprint
        except Exception as exc:
            logger.debug("Fingerprint failed for %s: %s", path, exc)
            return None, None

    def _probe_duration(self, path: Path) -> Optional[int]:
        """Probe audio duration using mutagen."""
        if MutagenFile is None:
            return None
        try:
            audio = MutagenFile(path)
            if audio and hasattr(audio, "info"):
                length = getattr(audio.info, "length", None)
                return int(length) if length else None
        except Exception:
            pass
        return None

    def _read_basic_tags(self, path: Path) -> dict[str, Optional[str]]:
        """Read basic tags from file."""
        if MutagenFile is None:
            return {}
        try:
            audio = MutagenFile(path, easy=True)
            if not audio or not audio.tags:
                return {}
            return {
                "artist": self._first_tag(audio, ["artist", "albumartist"]),
                "title": self._first_tag(audio, ["title"]),
                "album": self._first_tag(audio, ["album"]),
            }
        except Exception:
            return {}

    @staticmethod
    def _first_tag(audio, keys) -> Optional[str]:
        """Get first available tag value."""
        for key in keys:
            values = audio.tags.get(key)
            if values:
                return values[0] if isinstance(values, list) else values
        return None

    def _lookup_by_fingerprint(
        self,
        track: TrackInfo,
        duration: int,
        fingerprint: str,
        dir_release_id: Optional[str] = None,
    ) -> Optional[LookupResult]:
        """Lookup track by AcoustID fingerprint."""
        if acoustid is None:
            return None

        acoustic_matches = self._run_with_retries(
            lambda: acoustid.lookup(self.acoustid_api_key, fingerprint, duration),
            "AcoustID lookup",
            track.path,
        )
        if not acoustic_matches:
            return None

        for score, recording_id, title, artist in self._iter_acoustid(acoustic_matches):
            recording = self._fetch_recording(recording_id, track.path)
            if not recording:
                continue

            self._apply_recording(track, recording, title, artist, dir_release_id)
            track.match_source = "fingerprint"
            track.acoustid_id = recording_id
            track.match_confidence = score
            self.release_tracker.remember_release(track.path.parent, track.musicbrainz_release_id, score)
            return LookupResult(track, score=score)
        return None

    def _lookup_by_metadata(
        self,
        track: TrackInfo,
        tags: dict[str, Optional[str]],
        dir_release_id: Optional[str] = None,
    ) -> Optional[LookupResult]:
        """Lookup track by existing metadata tags."""
        if musicbrainzngs is None:
            return None

        artist = tags.get("artist")
        title = tags.get("title")
        if not artist or not title:
            return None

        response = self._run_with_retries(
            lambda: musicbrainzngs.search_recordings(
                artist=artist, recording=title, release=tags.get("album"), limit=1
            ),
            "MusicBrainz recording search",
            track.path,
        )
        if not response or not response.get("recording-list"):
            return None

        best = response["recording-list"][0]
        recording = self._fetch_recording(best["id"], track.path)
        if not recording:
            return None

        self._apply_recording(track, recording, best.get("title"), self._first_artist(recording), dir_release_id)

        score = float(best.get("ext-score", 0)) / 100.0
        track.musicbrainz_recording_id = best["id"]
        track.match_confidence = score
        self.release_tracker.remember_release(track.path.parent, track.musicbrainz_release_id, score)
        return LookupResult(track, score=score)

    def _lookup_by_guess(
        self,
        track: TrackInfo,
        guess: PathGuess,
        dir_release_id: Optional[str] = None,
    ) -> Optional[LookupResult]:
        """Lookup track by filename guess."""
        if musicbrainzngs is None or not guess.title:
            return None

        query: Dict[str, str] = {"recording": guess.title}
        if guess.artist:
            query["artist"] = guess.artist
        if guess.album:
            query["release"] = guess.album

        response = self._run_with_retries(
            lambda: musicbrainzngs.search_recordings(limit=3, **query),
            "MusicBrainz filename search",
            track.path,
        )
        if not response or not response.get("recording-list"):
            return None

        best = response["recording-list"][0]
        recording = self._fetch_recording(best["id"], track.path)
        if not recording:
            return None

        self._apply_recording(track, recording, best.get("title"), self._first_artist(recording), dir_release_id)

        score = float(best.get("ext-score", 0)) / 100.0 or guess.confidence()
        track.match_confidence = score
        self.release_tracker.remember_release(track.path.parent, track.musicbrainz_release_id, score)
        return LookupResult(track, score=score)

    def _apply_recording(
        self,
        track: TrackInfo,
        recording: dict,
        title: Optional[str],
        artist: Optional[str],
        preferred_release_id: Optional[str] = None,
    ) -> None:
        """Apply recording data to track."""
        release = self._select_release(recording, preferred_release_id)

        track.title = title or recording.get("title")
        track.artist = _normalize_artists(artist or self._first_artist(recording))
        track.album = release.get("title") if release else track.album
        release_artist = _normalize_artists(self._first_artist(release)) if release else None
        track.album_artist = release_artist or track.artist
        track.musicbrainz_recording_id = recording.get("id")
        track.musicbrainz_release_id = release.get("id") if release else track.musicbrainz_release_id

        # Extract classical music metadata
        work_rels = recording.get("work-relation-list", [])
        if work_rels:
            work = work_rels[0].get("work", {})
            track.work = work.get("title")
            track.composer = self._first_artist(work)

        for rel in recording.get("artist-relation-list", []):
            role = rel.get("type", "").lower()
            name = rel.get("artist", {}).get("name")
            if name:
                if role == "conductor":
                    track.conductor = name
                elif role in {"performer", "instrumentalist", "orchestra"}:
                    track.performer = name

    def _select_release(
        self,
        recording: dict,
        preferred_release_id: Optional[str],
    ) -> Optional[dict]:
        """Select best release from recording."""
        release_list = recording.get("release-list") or recording.get("releases") or []

        if preferred_release_id:
            for release in release_list:
                if release.get("id") == preferred_release_id:
                    return release

        return release_list[0] if release_list else None

    def _first_artist(self, entity: Optional[dict]) -> Optional[str]:
        """Extract first artist name from entity."""
        if not entity:
            return None
        credits = entity.get("artist-credit", [])
        if not credits:
            return None

        names = []
        for credit in credits:
            if isinstance(credit, str) and credit.strip():
                names.append(credit.strip())
            elif isinstance(credit, dict):
                if "name" in credit:
                    names.append(credit["name"])
                elif isinstance(credit.get("artist"), dict) and credit["artist"].get("name"):
                    names.append(credit["artist"]["name"])
        return ", ".join(names) if names else None

    def _iter_acoustid(self, response):
        """Iterate over AcoustID response."""
        for match in response.get("results", []):
            score = float(match.get("score", 0))
            for recording in match.get("recordings", []):
                rec_id = recording.get("id")
                if not rec_id:
                    continue
                artists = recording.get("artists") or []
                artist_name = (
                    artists[0]["name"]
                    if artists and isinstance(artists[0], dict) and "name" in artists[0]
                    else None
                )
                yield score, rec_id, recording.get("title"), artist_name

    def _fetch_recording(self, recording_id: str, path: Path) -> Optional[dict]:
        """Fetch recording from MusicBrainz with caching."""
        if musicbrainzngs is None:
            return None

        if self.cache:
            cached = self.cache.get_mb_recording(recording_id)
            if cached:
                return cached

        recording = self._run_with_retries(
            lambda: musicbrainzngs.get_recording_by_id(
                recording_id, includes=["artists", "releases", "work-rels", "artist-credits"]
            )["recording"],
            "MusicBrainz recording fetch",
            path,
        )
        if recording and self.cache:
            self.cache.set_mb_recording(recording_id, recording)
        return recording

    def _fetch_release_tracks(self, release_id: str) -> Optional[ReleaseData]:
        """Fetch release with track listing."""
        if musicbrainzngs is None:
            return None

        if self.cache:
            cached = self.cache.get_mb_release(release_id)
            if cached:
                return self._build_release_data(cached)

        release = self._run_with_retries(
            lambda: musicbrainzngs.get_release_by_id(
                release_id, includes=["recordings", "artist-credits", "media"]
            )["release"],
            "MusicBrainz release fetch",
            Path(release_id),
        )
        if not release:
            return None

        if self.cache:
            self.cache.set_mb_release(release_id, release)
        return self._build_release_data(release)

    def _build_release_data(self, release: dict) -> ReleaseData:
        """Build ReleaseData from MusicBrainz release."""
        release_id = release.get("id")
        if not release_id:
            raise ValueError("release payload missing id")

        data = ReleaseData(
            release_id,
            release.get("title"),
            self._first_artist(release),
            release.get("date"),
        )

        media = release.get("medium-list", [])
        data.disc_count = len(media)

        for medium_index, medium in enumerate(media, start=1):
            formats = medium.get("format-list") or (
                [medium.get("format")] if medium.get("format") else []
            )
            for fmt in formats:
                if fmt and fmt not in data.formats:
                    data.formats.append(fmt)

            track_list = medium.get("track-list", []) or []
            for index, track in enumerate(track_list, start=1):
                recording = track.get("recording", {})
                number = self._parse_track_number(track.get("number")) or index
                length = track.get("length")
                duration = int(length) // 1000 if length else None

                data.add_track(
                    ReleaseTrack(
                        recording_id=recording.get("id"),
                        disc_number=medium_index,
                        number=number,
                        title=recording.get("title"),
                        duration_seconds=duration,
                    )
                )

        return data

    @staticmethod
    def _parse_track_number(value: Optional[str]) -> Optional[int]:
        """Parse track number from string."""
        if not value:
            return None
        cleaned = value.strip()
        if cleaned.isdigit():
            return int(cleaned)
        # Try "disc/track" format
        match = re.match(r"^\s*\d+\s*[-./]\s*(\d+)\s*$", cleaned)
        if match:
            return int(match.group(1))
        # Try letter (A=1, B=2, etc.)
        match = re.match(r"^\s*([A-Za-z])\s*$", cleaned)
        if match:
            return ord(match.group(1).upper()) - ord("A") + 1
        # Extract digits
        digits = "".join(ch for ch in cleaned if ch.isdigit())
        return int(digits) if digits else None

    def _apply_release_match(
        self, track: TrackInfo, release_match: ReleaseMatch
    ) -> Optional[LookupResult]:
        """Apply a release match to track."""
        recording = self._fetch_recording(release_match.track.recording_id, track.path)
        if not recording:
            return None

        self._apply_recording(
            track,
            recording,
            release_match.track.title or recording.get("title"),
            self._first_artist(recording),
            release_match.release.release_id,
        )

        track.match_confidence = max(track.match_confidence or 0.0, release_match.confidence)
        self._after_match(track)
        self.release_tracker.remember_release(track.path.parent, track.musicbrainz_release_id, release_match.confidence)
        return LookupResult(track, score=release_match.confidence)

    def _after_match(self, track: TrackInfo) -> None:
        """Post-match processing."""
        release_id = track.musicbrainz_release_id
        if not release_id:
            return

        self.release_tracker.register(
            track.path.parent,
            release_id,
            self._fetch_release_tracks,
            matched_recording_id=track.musicbrainz_recording_id,
        )

        release = self.release_tracker.releases.get(release_id)
        if release:
            if not track.album:
                track.album = release.album_title
            if not track.album_artist:
                track.album_artist = release.album_artist

    def _run_with_retries(self, fn, label: str, path: Path):
        """Run function with retry logic."""
        last_exc = None
        for attempt in range(max(1, 1 + self.network_retries)):
            try:
                return fn()
            except Exception as exc:
                if not self._is_transient_network_error(exc):
                    raise
                last_exc = exc
                if attempt < self.network_retries:
                    time.sleep(self.retry_backoff * (2 ** attempt))

        if last_exc:
            self._note_network_failure(label=label, path=path, exc=last_exc)
        return None

    def _note_network_failure(self, *, label: str, path: Path, exc: Exception) -> None:
        """Note network failure and apply cooldown."""
        now = time.time()
        self._network_disabled_until = max(self._network_disabled_until, now + 30.0)
        if now - self._last_network_warning >= 10.0:
            self._last_network_warning = now
            logger.warning("%s failed for %s: %s", label, path, exc)

    @staticmethod
    def _is_transient_network_error(exc: Exception) -> bool:
        """Check if exception is a transient network error."""
        if isinstance(exc, (socket.gaierror, urllib.error.URLError, TimeoutError, ConnectionError)):
            return True
        if musicbrainzngs is not None:
            network_err = getattr(musicbrainzngs, "NetworkError", None)
            if network_err and isinstance(exc, network_err):
                return True
        return False


def _normalize_title(value: Optional[str]) -> Optional[str]:
    """Normalize title for matching."""
    if not value:
        return None

    import unicodedata
    cleaned = unicodedata.normalize("NFKD", value)
    cleaned = cleaned.replace("&", " and ").encode("ascii", "ignore").decode("ascii").lower()
    cleaned = re.sub(r"^\s*\d{1,3}\s*[-–—_.]+\s*", "", cleaned)
    cleaned = re.sub(r"\s*[\(\[]\s*(remaster(?:ed)?|mono|stereo|live|bonus)\s*[\)\]]\s*$", "", cleaned)
    cleaned = re.sub(r"[^\w\s]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _normalize_artists(value: Optional[str]) -> Optional[str]:
    """Normalize artist names."""
    if not value:
        return None
    tokens = [chunk.strip() for chunk in re.split(r"[;,]+", value) if chunk.strip()]
    connectors = {"&", "and", "with", "feat", "featuring", "+"}
    unique = []
    for token in tokens:
        base = token.split(" (", 1)[0].strip()
        if base and base.lower() not in connectors and base not in unique:
            unique.append(base)
    return ", ".join(unique) if unique else None
