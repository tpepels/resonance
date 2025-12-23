"""AcoustID provider for fingerprint-based music identification.

This module implements the AcoustID provider client that searches for music
releases using audio fingerprints. AcoustID provides content-based identification
that is independent of metadata tags.

API Documentation: https://acoustid.org/webservice
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Optional

from resonance.core.identifier import ProviderCapabilities, ProviderClient, ProviderRelease
from resonance.infrastructure.cache import MetadataCache


class AcoustIDClient(ProviderClient):
    """AcoustID provider client for fingerprint-based identification.

    AcoustID uses audio fingerprints to identify recordings and their associated
    MusicBrainz metadata. This provides content-based identification that works
    even when tags are missing or incorrect.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.acoustid.org/v2",
        cache: Optional[MetadataCache] = None,
    ) -> None:
        """Initialize the AcoustID client.

        Args:
            api_key: AcoustID API key. If None, reads from ACOUSTID_API_KEY env var.
            base_url: Base URL for the AcoustID API
            cache: MetadataCache for responses
        """
        self.api_key = api_key or os.getenv("ACOUSTID_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.cache = cache

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Declare AcoustID capabilities."""
        return ProviderCapabilities(
            supports_fingerprints=True,
            supports_metadata=False,  # AcoustID doesn't support metadata-only search
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        """Search for releases using audio fingerprints.

        Args:
            fingerprints: List of fingerprint strings

        Returns:
            List of provider releases, deterministically ordered
        """
        if not fingerprints:
            return []

        try:
            # Lazy import to handle cases where pyacoustid isn't available
            # Note: pyacoustid 1.3.0+ uses 'acoustid' as the module name
            import acoustid as pyacoustid
        except ImportError:
            try:
                # Fallback for older versions
                import pyacoustid
            except ImportError:
                # Graceful degradation if pyacoustid not available
                return []

        # Check cache first if available
        cache_key = None
        if self.cache:
            cache_key = AcoustIDCache.make_cache_key(fingerprints)
            cached_result = self.cache.get(cache_key)
            if cached_result:
                return self._parse_cached_results(cached_result)

        # Perform AcoustID lookup
        try:
            # pyacoustid.lookup() expects individual fingerprint strings
            # We'll look up the first fingerprint for now (can be extended for multiple)
            fingerprint = fingerprints[0]

            results = pyacoustid.lookup(
                fingerprint,
                self.base_url + "/lookup",
                self.api_key,
                meta=["recordings", "releases"],
            )

            releases = self._parse_acoustid_results(results)

            # Cache the results if cache is available
            if self.cache and cache_key:
                self.cache.set(
                    cache_key, self._serialize_results(releases), namespace="acoustid:lookup"
                )

            return releases

        except pyacoustid.AcoustidError:
            # Handle AcoustID API errors gracefully
            # Could be rate limiting, invalid API key, network issues, etc.
            return []

        except Exception:
            # Handle unexpected errors gracefully
            return []

    def _parse_cached_results(self, cached_data: dict[str, Any]) -> list[ProviderRelease]:
        """Parse cached AcoustID results.

        Args:
            cached_data: Cached response data

        Returns:
            List of ProviderRelease objects
        """
        # Placeholder implementation - would deserialize cached data
        return []

    def _parse_acoustid_results(self, results: list[dict[str, Any]]) -> list[ProviderRelease]:
        """Parse AcoustID API response into ProviderRelease objects.

        Args:
            results: Raw AcoustID API response

        Returns:
            List of ProviderRelease objects, deterministically ordered
        """
        from resonance.core.identifier import ProviderTrack

        releases: list[ProviderRelease] = []

        for result in results:
            # Each result represents a recording match
            score = result.get("score", 0)
            if score < 0.5:  # Skip low-confidence matches
                continue

            recordings = result.get("recordings", [])
            for recording in recordings:
                # Extract basic recording information
                title = recording.get("title", "Unknown Title")
                artists = recording.get("artists", [])
                artist = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"

                # For now, create a "pseudo-release" from the recording
                # In a full implementation, we'd resolve to actual releases via MusicBrainz
                release_id = recording.get("id", "unknown")
                if release_id == "unknown":
                    continue

                # Create a single track for this recording
                track = ProviderTrack(
                    position=1,
                    title=title,
                    duration_seconds=None,  # AcoustID doesn't provide duration in lookup
                    fingerprint_id=None,  # We don't have the original fingerprint here
                )

                release = ProviderRelease(
                    provider="acoustid",
                    release_id=f"acoustid-{release_id}",
                    title=title,
                    artist=artist,
                    tracks=(track,),
                    year=None,
                    release_kind=None,
                )

                releases.append(release)

        # Sort deterministically by score (highest first), then by release_id
        releases.sort(key=lambda r: (-result.get("score", 0), r.release_id))

        return releases

    def _serialize_results(self, releases: list[ProviderRelease]) -> dict[str, Any]:
        """Serialize ProviderRelease objects for caching.

        Args:
            releases: List of ProviderRelease objects

        Returns:
            Serializable data structure
        """
        # Placeholder implementation - would serialize releases for caching
        return {"releases": [], "timestamp": None}

    def search_by_metadata(
        self, artist: Optional[str], album: Optional[str], track_count: int
    ) -> list[ProviderRelease]:
        """AcoustID does not support metadata-only search.

        This method exists to satisfy the ProviderClient interface but always
        returns empty results since AcoustID requires fingerprints.
        """
        return []


class AcoustIDCache:
    """Cache for AcoustID API responses."""

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        """Initialize the cache.

        Args:
            cache_dir: Directory to store cache files (optional)
        """
        self.cache_dir = cache_dir

    def get(self, key: str) -> Optional[dict[str, Any]]:
        """Get cached response for a key.

        Args:
            key: Cache key

        Returns:
            Cached response data or None
        """
        # Placeholder - will be implemented when needed
        return None

    def put(self, key: str, data: dict[str, Any]) -> None:
        """Store response data in cache.

        Args:
            key: Cache key
            data: Response data to cache
        """
        # Placeholder - will be implemented when needed
        pass

    @staticmethod
    def make_cache_key(
        fingerprints: list[str],
        client_version: str = "1.0",
    ) -> str:
        """Create a deterministic cache key for fingerprint queries.

        Args:
            fingerprints: List of fingerprint strings
            client_version: Client version for cache invalidation

        Returns:
            Cache key string
        """
        # Sort fingerprints for deterministic ordering
        sorted_fps = sorted(fingerprints)

        # Create hash of fingerprints
        fp_hash = hashlib.sha256()
        for fp in sorted_fps:
            fp_hash.update(fp.encode("utf-8"))

        # Include client version for cache invalidation
        key_data = {
            "fingerprints_hash": fp_hash.hexdigest(),
            "fingerprint_count": len(sorted_fps),
            "client_version": client_version,
        }

        # Create final key hash
        key_hash = hashlib.sha256()
        key_hash.update(json.dumps(key_data, sort_keys=True).encode("utf-8"))

        return key_hash.hexdigest()
