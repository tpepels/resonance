"""Discogs provider client for V3 identification."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from resonance import __version__ as RESONANCE_VERSION
from resonance.core.identifier import ProviderCapabilities, ProviderClient, ProviderRelease, ProviderTrack
from resonance.core.identity import display_album, display_artist, display_work, match_key_artist
from resonance.infrastructure.cache import MetadataCache

_CACHE_VERSION = "v1"
_SEARCH_LIMIT = 10

logger = logging.getLogger(__name__)


class DiscogsClient(ProviderClient):
    """Discogs client that returns ProviderRelease candidates."""

    def __init__(
        self,
        token: str,
        *,
        useragent: Optional[str] = None,
        cache: MetadataCache | None = None,
        offline: bool = False,
    ) -> None:
        if not token:
            raise ValueError("Discogs token required")
        self._token = token
        self._useragent = useragent or f"resonance/{RESONANCE_VERSION}"
        self._cache = cache
        self._offline = offline

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=False,  # Discogs does not support fingerprint search
            supports_metadata=True,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        """Discogs does not support fingerprint search."""
        _ = fingerprints
        return []

    def search_by_metadata(
        self, artist: Optional[str], album: Optional[str], track_count: int
    ) -> list[ProviderRelease]:
        """Search Discogs by metadata and canonicalize results."""
        _ = track_count
        if self._offline:
            return []

        params: dict[str, str] = {
            "token": self._token,
            "type": "release",
            "per_page": str(_SEARCH_LIMIT),
        }
        if artist:
            params["artist"] = artist
        if album:
            params["release_title"] = album

        url = f"https://api.discogs.com/database/search?{urllib.parse.urlencode(params)}"
        payload = self._request(url)
        if not payload:
            return []

        results = payload.get("results", [])
        releases: list[ProviderRelease] = []
        for result in results:
            release_id = result.get("id")
            if not release_id:
                continue
            details = self._fetch_release(int(release_id))
            if not details:
                continue
            releases.append(self._release_from_payload(result, details))

        releases.sort(key=lambda entry: entry.release_id)
        return releases

    def _fetch_release(self, release_id: int) -> Optional[dict]:
        if self._cache:
            cached = self._cache.get_discogs_release(
                str(release_id),
                cache_version=_CACHE_VERSION,
                client_version=RESONANCE_VERSION,
            )
            if cached is not None:
                logger.debug("Discogs cache hit for release %s", release_id)
                return cached

        url = f"https://api.discogs.com/releases/{release_id}?token={self._token}"
        payload = self._request(url)
        if payload and self._cache:
            logger.debug("Discogs cache miss; storing release %s", release_id)
            self._cache.set_discogs_release(
                str(release_id),
                payload,
                cache_version=_CACHE_VERSION,
                client_version=RESONANCE_VERSION,
            )
        return payload

    def _request(self, url: str) -> Optional[dict]:
        if self._offline:
            return None
        request = urllib.request.Request(url, headers={"User-Agent": self._useragent})
        try:
            with urllib.request.urlopen(request, timeout=10) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            logger.debug("Discogs HTTP error %s for %s: %s", exc.code, url, exc)
        except urllib.error.URLError as exc:
            logger.warning("Discogs request failed for %s: %s", url, exc)
        return None

    def _release_from_payload(self, result: dict, details: dict) -> ProviderRelease:
        release_id = str(details.get("id") or result.get("id"))
        title = result.get("release_title") or result.get("title")
        artist = result.get("artist")
        parsed_artist, parsed_title = self._split_search_title(title)
        if not artist:
            artist = parsed_artist
        if parsed_title:
            title = parsed_title
        if not title:
            title = details.get("title") or "Unknown"
        if not artist:
            artist = self._join_artists(details.get("artists", [])) or "Unknown"

        year = result.get("year") or details.get("year")
        tracks = self._parse_tracklist(details.get("tracklist", []))
        release_kind = self._infer_release_kind(
            title=title,
            track_count=len(tracks),
            formats=details.get("formats") or [],
        )
        return ProviderRelease(
            provider="discogs",
            release_id=release_id,
            title=display_album(title),
            artist=display_artist(artist),
            tracks=tracks,
            year=year,
            release_kind=release_kind,
        )

    def _parse_tracklist(self, tracklist: list[dict]) -> tuple[ProviderTrack, ...]:
        tracks: list[ProviderTrack] = []
        fallback_position = 1
        for entry in tracklist:
            if entry.get("type_") in {"heading", "index"}:
                continue
            title = entry.get("title")
            if not title:
                continue
            disc_number, position = self._parse_track_position(entry.get("position"))
            if position is None:
                position = fallback_position
            fallback_position += 1
            tracks.append(
                ProviderTrack(
                    position=position,
                    title=display_work(title),
                    duration_seconds=self._parse_duration(entry.get("duration")),
                    disc_number=disc_number,
                )
            )
        return tuple(tracks)

    def _parse_track_position(self, position: Optional[str]) -> tuple[Optional[int], Optional[int]]:
        if not position:
            return None, None
        cleaned = position.strip()
        if not cleaned:
            return None, None

        if cleaned.isdigit():
            return None, int(cleaned)

        match = re.match(r"^\s*[A-Za-z]*\s*(\d+)\s*[-./]\s*(\d+)\s*$", cleaned)
        if match:
            return int(match.group(1)), int(match.group(2))

        match = re.match(r"^\s*([A-Za-z])\s*$", cleaned)
        if match:
            return None, ord(match.group(1).upper()) - ord("A") + 1

        match = re.match(r"^\s*[A-Za-z]+\s*(\d+)\s*$", cleaned)
        if match:
            return None, int(match.group(1))

        digits = "".join(ch for ch in cleaned if ch.isdigit())
        return None, int(digits) if digits else None

    def _parse_duration(self, value: Optional[str]) -> Optional[int]:
        if not value or ":" not in value:
            return None
        try:
            minutes, seconds = value.split(":", 1)
            return int(minutes) * 60 + int(seconds)
        except ValueError:
            return None

    def _join_artists(self, artists: list[dict]) -> Optional[str]:
        names: list[str] = []
        for artist in artists:
            name = artist.get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return self._normalize_artist_string(", ".join(names))

    def _normalize_artist_string(self, value: str) -> Optional[str]:
        if not value:
            return None
        cleaned: list[str] = []
        for chunk in re.split(r"[;,]+", value):
            base = chunk.split(" (")[0].strip()
            if base:
                cleaned.append(display_artist(base))

        unique: list[str] = []
        seen: set[str] = set()
        for entry in cleaned:
            token = match_key_artist(entry) or entry.casefold()
            if token and token not in seen:
                unique.append(entry)
                seen.add(token)
        return ", ".join(unique) if unique else None

    def _infer_release_kind(
        self, *, title: str, track_count: int, formats: list[dict]
    ) -> Optional[str]:
        title_lower = title.casefold()
        if "ep" in title_lower.split():
            return "ep"
        if "single" in title_lower.split():
            return "single"
        for fmt in formats:
            if not isinstance(fmt, dict):
                continue
            name = fmt.get("name")
            descriptions = fmt.get("descriptions") or []
            tokens = []
            if isinstance(name, str):
                tokens.append(name.casefold())
            if isinstance(descriptions, list):
                tokens.extend(
                    desc.casefold() for desc in descriptions if isinstance(desc, str)
                )
            if "single" in tokens:
                return "single"
            if "ep" in tokens:
                return "ep"
        if track_count <= 2:
            return "single"
        if track_count <= 6:
            return "ep"
        return "album"

    @staticmethod
    def _split_search_title(value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not value or " - " not in value:
            return None, None
        parts = value.split(" - ", 1)
        artist = parts[0].strip() or None
        title = parts[1].strip() or None
        return artist, title
