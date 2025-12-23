"""Provider fusion utilities for deterministic multi-provider queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from resonance.core.identifier import ProviderCapabilities, ProviderClient, ProviderRelease
from resonance.core.identity import match_key_album, match_key_artist, match_key_work


@dataclass(frozen=True)
class NamedProvider:
    name: str
    client: ProviderClient


class CombinedProviderClient(ProviderClient):
    """Combine multiple providers with deterministic ordering and de-dupe."""

    def __init__(
        self,
        providers: Iterable[NamedProvider],
        *,
        provider_priority: tuple[str, ...] = ("musicbrainz", "discogs"),
    ) -> None:
        self._providers = tuple(providers)
        self._priority = {name: index for index, name in enumerate(provider_priority)}

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Aggregate capabilities from all providers."""
        supports_fingerprints = any(
            provider.client.capabilities.supports_fingerprints
            for provider in self._providers
        )
        supports_metadata = any(
            provider.client.capabilities.supports_metadata
            for provider in self._providers
        )
        return ProviderCapabilities(
            supports_fingerprints=supports_fingerprints,
            supports_metadata=supports_metadata,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        releases = self._collect(lambda client: client.search_by_fingerprints(fingerprints))
        return self._dedupe_and_sort(releases)

    def search_by_metadata(
        self, artist: str | None, album: str | None, track_count: int
    ) -> list[ProviderRelease]:
        releases = self._collect(
            lambda client: client.search_by_metadata(artist, album, track_count)
        )
        return self._dedupe_and_sort(releases)

    def _collect(self, fn) -> list[ProviderRelease]:
        releases: list[ProviderRelease] = []
        for named in self._providers:
            try:
                result = fn(named.client)
            except Exception:
                continue
            releases.extend(self._ensure_provider(name=named.name, releases=result))
        return releases

    def _ensure_provider(self, *, name: str, releases: Iterable[ProviderRelease]) -> list[ProviderRelease]:
        normalized: list[ProviderRelease] = []
        for release in releases:
            if release.provider == name:
                normalized.append(release)
                continue
            normalized.append(
                ProviderRelease(
                    provider=name,
                    release_id=release.release_id,
                    title=release.title,
                    artist=release.artist,
                    tracks=release.tracks,
                    year=release.year,
                    release_kind=release.release_kind,
                )
            )
        return normalized

    def _dedupe_and_sort(self, releases: list[ProviderRelease]) -> list[ProviderRelease]:
        deduped: dict[tuple, ProviderRelease] = {}
        for release in releases:
            track_key = tuple(
                (
                    track.position,
                    track.fingerprint_id
                    or match_key_work(track.title)
                    or track.title.casefold(),
                )
                for track in release.tracks
            )
            key = (
                match_key_album(release.title) or release.title.casefold(),
                match_key_artist(release.artist) or release.artist.casefold(),
                track_key,
            )
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = release
                continue
            if self._priority.get(release.provider, 99) < self._priority.get(
                existing.provider, 99
            ):
                deduped[key] = release

        def sort_key(item: ProviderRelease) -> tuple[int, str]:
            return (self._priority.get(item.provider, 99), item.release_id)

        return sorted(deduped.values(), key=sort_key)
