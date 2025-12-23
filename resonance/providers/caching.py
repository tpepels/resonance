"""Caching and offline wrapper for ProviderClient implementations.

Phase C.3 minimal slice: Cache-first read path with offline mode enforcement.

This wrapper provides:
- Cache-first read path with stable, versioned keys
- Write-through on success
- Offline mode: cache hit → proceed, cache miss → deterministic error
- All HTTP calls eliminated on second run (cache hit)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from resonance.core.identifier import ProviderClient, ProviderRelease
from resonance.errors import RuntimeFailure
from resonance.infrastructure.cache import MetadataCache
from resonance.infrastructure.provider_cache import provider_cache_key


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for a cached provider client."""

    # Provider identifier (e.g., "musicbrainz", "discogs")
    provider_name: str

    # Client version - cache invalidation when implementation changes
    client_version: str

    # Cache schema version - cache invalidation when DTO shape changes
    cache_version: str = "v1"

    # Offline mode: cache miss → error instead of network call
    offline: bool = False


class CachedProviderClient(ProviderClient):
    """Wrapper that adds cache-first + offline semantics to a ProviderClient.

    **Cache semantics:**
    - First call: fetch from provider, write to cache
    - Second call: read from cache, no HTTP
    - Cache key: provider + method + normalized request + version

    **Offline semantics:**
    - offline=False: cache miss → call provider (normal mode)
    - offline=True + cache hit → return cached result
    - offline=True + cache miss → raise RuntimeFailure("needs network")

    **Acceptance criteria:**
    - Test can assert: "second run performs zero HTTP calls"
    - Test can assert: "offline mode never attempts network"
    - Test can assert: "offline + cache hit works"
    - Test can assert: "offline + cache miss yields deterministic error"
    """

    def __init__(
        self,
        provider: ProviderClient,
        cache: MetadataCache,
        config: ProviderConfig,
    ) -> None:
        """Initialize cached provider wrapper.

        Args:
            provider: Underlying provider client (makes HTTP calls)
            cache: MetadataCache instance for persistence
            config: Provider configuration (name, version, offline mode)
        """
        self._provider = provider
        self._cache = cache
        self._config = config

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        """Search by fingerprints with cache-first semantics.

        Cache key: provider:search_by_fingerprints:version:client_version:fps=<sorted_fps>

        Returns:
            Cached or fresh list of ProviderRelease
        """
        # Build stable cache key
        # Sort fingerprints to ensure stable key regardless of input order
        sorted_fps = sorted(fingerprints)
        cache_key = provider_cache_key(
            provider=self._config.provider_name,
            request_type="search_by_fingerprints",
            query={"fingerprints": ",".join(sorted_fps)},
            version=self._config.cache_version,
            client_version=self._config.client_version,
        )

        # Cache-first read
        cached = self._cache.get(cache_key, namespace=f"{self._config.provider_name}:search")
        if cached is not None:
            # Cache hit - deserialize to ProviderRelease objects
            return self._deserialize_releases(cached)

        # Cache miss
        if self._config.offline:
            # Offline mode: deterministic error on cache miss
            raise RuntimeFailure(
                f"Provider {self._config.provider_name} requires network "
                f"(offline mode, cache miss for fingerprint search)"
            )

        # Online mode: call provider
        releases = self._provider.search_by_fingerprints(fingerprints)

        # Write-through to cache
        self._cache.set(
            cache_key,
            self._serialize_releases(releases),
            namespace=f"{self._config.provider_name}:search",
        )

        return releases

    def search_by_metadata(
        self, artist: Optional[str], album: Optional[str], track_count: int
    ) -> list[ProviderRelease]:
        """Search by metadata with cache-first semantics.

        Cache key: provider:search_by_metadata:version:client_version:artist=X|album=Y|track_count=Z

        Returns:
            Cached or fresh list of ProviderRelease
        """
        # Build stable cache key
        query_parts = {}
        if artist is not None:
            query_parts["artist"] = artist
        if album is not None:
            query_parts["album"] = album
        query_parts["track_count"] = str(track_count)

        cache_key = provider_cache_key(
            provider=self._config.provider_name,
            request_type="search_by_metadata",
            query=query_parts,
            version=self._config.cache_version,
            client_version=self._config.client_version,
        )

        # Cache-first read
        cached = self._cache.get(cache_key, namespace=f"{self._config.provider_name}:search")
        if cached is not None:
            # Cache hit - deserialize to ProviderRelease objects
            return self._deserialize_releases(cached)

        # Cache miss
        if self._config.offline:
            # Offline mode: deterministic error on cache miss
            raise RuntimeFailure(
                f"Provider {self._config.provider_name} requires network "
                f"(offline mode, cache miss for metadata search: "
                f"artist={artist!r}, album={album!r}, track_count={track_count})"
            )

        # Online mode: call provider
        releases = self._provider.search_by_metadata(artist, album, track_count)

        # Write-through to cache
        self._cache.set(
            cache_key,
            self._serialize_releases(releases),
            namespace=f"{self._config.provider_name}:search",
        )

        return releases

    def _serialize_releases(self, releases: list[ProviderRelease]) -> list[dict]:
        """Convert ProviderRelease objects to JSON-serializable dicts."""
        return [
            {
                "provider": release.provider,
                "release_id": release.release_id,
                "title": release.title,
                "artist": release.artist,
                "tracks": [
                    {
                        "position": track.position,
                        "title": track.title,
                        "duration_seconds": track.duration_seconds,
                        "fingerprint_id": track.fingerprint_id,
                        "composer": track.composer,
                        "disc_number": track.disc_number,
                        "recording_id": track.recording_id,
                    }
                    for track in release.tracks
                ],
                "year": release.year,
                "release_kind": release.release_kind,
            }
            for release in releases
        ]

    def _deserialize_releases(self, data: list[dict]) -> list[ProviderRelease]:
        """Convert JSON-serializable dicts to ProviderRelease objects."""
        from resonance.core.identifier import ProviderTrack

        releases: list[ProviderRelease] = []
        for release_data in data:
            tracks = tuple(
                ProviderTrack(
                    position=track["position"],
                    title=track["title"],
                    duration_seconds=track.get("duration_seconds"),
                    fingerprint_id=track.get("fingerprint_id"),
                    composer=track.get("composer"),
                    disc_number=track.get("disc_number"),
                    recording_id=track.get("recording_id"),
                )
                for track in release_data["tracks"]
            )
            releases.append(
                ProviderRelease(
                    provider=release_data["provider"],
                    release_id=release_data["release_id"],
                    title=release_data["title"],
                    artist=release_data["artist"],
                    tracks=tracks,
                    year=release_data.get("year"),
                    release_kind=release_data.get("release_kind"),
                )
            )
        return releases
