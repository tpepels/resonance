"""MusicBrainz provider client for V3 identification."""

from __future__ import annotations

import logging
import re
from typing import Optional

from resonance import __version__ as RESONANCE_VERSION
from resonance.core.identifier import ProviderCapabilities, ProviderClient, ProviderRelease, ProviderTrack
from resonance.core.identity import display_album, display_artist, display_work, match_key_artist
from resonance.infrastructure.cache import MetadataCache

try:
    import musicbrainzngs
except ModuleNotFoundError:  # pragma: no cover - exercised in tests via monkeypatch
    musicbrainzngs = None

_CACHE_VERSION = "v1"
_SEARCH_LIMIT = 10

logger = logging.getLogger(__name__)


class MusicBrainzClient(ProviderClient):
    """MusicBrainz client that returns ProviderRelease candidates."""

    def __init__(
        self,
        acoustid_api_key: Optional[str] = None,
        *,
        useragent: Optional[str] = None,
        cache: MetadataCache | None = None,
        offline: bool = False,
    ) -> None:
        _ = acoustid_api_key
        self._cache = cache
        self._offline = offline
        if musicbrainzngs is not None:
            musicbrainzngs.set_useragent("resonance", RESONANCE_VERSION, contact=useragent)

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=False,  # Not implemented yet
            supports_metadata=True,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        """Fingerprint search is not implemented in the V3 client yet."""
        _ = fingerprints
        return []

    def search_by_metadata(
        self, artist: Optional[str], album: Optional[str], track_count: int
    ) -> list[ProviderRelease]:
        _ = track_count
        if self._offline or musicbrainzngs is None:
            return []

        payload = musicbrainzngs.search_releases(
            artist=artist,
            release=album,
            limit=_SEARCH_LIMIT,
        )
        releases = payload.get("release-list", [])
        results: list[ProviderRelease] = []
        for release in releases:
            release_id = release.get("id")
            if not release_id:
                continue
            details = self._fetch_release(release_id)
            if not details:
                continue
            results.append(self._build_release(details))

        results.sort(key=lambda entry: entry.release_id)
        return results

    def _fetch_release(self, release_id: str) -> Optional[dict]:
        if self._cache:
            cached = self._cache.get_mb_release(
                release_id,
                cache_version=_CACHE_VERSION,
                client_version=RESONANCE_VERSION,
            )
            if cached is not None:
                logger.debug("MusicBrainz cache hit for release %s", release_id)
                return cached

        if musicbrainzngs is None or self._offline:
            return None

        payload = musicbrainzngs.get_release_by_id(
            release_id,
            includes=["recordings", "artist-credits", "media"],
        )
        release = payload.get("release")
        if release and self._cache:
            self._cache.set_mb_release(
                release_id,
                release,
                cache_version=_CACHE_VERSION,
                client_version=RESONANCE_VERSION,
            )
        return release

    def _build_release(self, release: dict) -> ProviderRelease:
        release_id = release.get("id")
        if not release_id:
            raise ValueError("MusicBrainz release payload missing id")

        title = display_album(release.get("title") or "Unknown")
        artist = self._canonicalize_artist_credit(release.get("artist-credit", []))
        year = self._parse_year(release.get("date"))
        tracks = self._parse_media_tracks(release.get("medium-list", []))
        release_kind = self._infer_release_kind(
            track_count=len(tracks),
            release_group=release.get("release-group") or {},
        )

        return ProviderRelease(
            provider="musicbrainz",
            release_id=release_id,
            title=title,
            artist=artist or "Unknown",
            tracks=tracks,
            year=year,
            release_kind=release_kind,
        )

    def _parse_media_tracks(self, media: list[dict]) -> tuple[ProviderTrack, ...]:
        ordered_media = sorted(
            enumerate(media, start=1),
            key=lambda item: (
                item[1].get("position") or item[0],
                item[0],
            ),
        )
        tracks: list[ProviderTrack] = []
        for fallback_disc, medium in ordered_media:
            disc_number = medium.get("position") or fallback_disc
            track_list = medium.get("track-list", []) or []
            for index, track in enumerate(track_list, start=1):
                recording = track.get("recording") or {}
                position = (
                    self._parse_track_number(track.get("number"))
                    or track.get("position")
                    or index
                )
                duration_ms = track.get("length")
                duration_seconds = int(duration_ms) // 1000 if duration_ms else None
                title = recording.get("title") or track.get("title") or "Unknown"
                tracks.append(
                    ProviderTrack(
                        position=int(position),
                        title=display_work(title),
                        duration_seconds=duration_seconds,
                        disc_number=int(disc_number) if disc_number is not None else None,
                        recording_id=recording.get("id"),
                    )
                )
        return tuple(tracks)

    def _canonicalize_artist_credit(self, credits: list) -> Optional[str]:
        names: list[str] = []
        for credit in credits:
            if isinstance(credit, str) and credit.strip():
                names.append(credit.strip())
            elif isinstance(credit, dict):
                name = credit.get("name")
                artist = credit.get("artist")
                if name:
                    names.append(name)
                elif isinstance(artist, dict) and artist.get("name"):
                    names.append(artist["name"])

        unique: list[str] = []
        seen: set[str] = set()
        for entry in names:
            display = display_artist(entry)
            token = match_key_artist(display) or display.casefold()
            if token and token not in seen:
                unique.append(display)
                seen.add(token)

        return ", ".join(unique) if unique else None

    def _infer_release_kind(self, track_count: int, release_group: dict) -> Optional[str]:
        primary = release_group.get("primary-type")
        if isinstance(primary, str):
            primary_lower = primary.casefold()
            if primary_lower in {"single", "ep", "album"}:
                return primary_lower
        if track_count <= 2:
            return "single"
        if track_count <= 6:
            return "ep"
        return "album"

    @staticmethod
    def _parse_year(value: Optional[str]) -> Optional[int]:
        if not value:
            return None
        year = value.split("-", 1)[0]
        return int(year) if year.isdigit() else None

    @staticmethod
    def _parse_track_number(value: Optional[str]) -> Optional[int]:
        if not value:
            return None
        cleaned = value.strip()
        if cleaned.isdigit():
            return int(cleaned)
        match = re.match(r"^\s*\d+\s*[-./]\s*(\d+)\s*$", cleaned)
        if match:
            return int(match.group(1))
        match = re.match(r"^\s*([A-Za-z])\s*$", cleaned)
        if match:
            return ord(match.group(1).upper()) - ord("A") + 1
        digits = "".join(ch for ch in cleaned if ch.isdigit())
        return int(digits) if digits else None
