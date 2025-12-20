"""Identity canonicalization - applies canonical name mappings.

This module provides business logic for applying canonical identity mappings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .matching import normalize_token

if TYPE_CHECKING:
    from pathlib import Path


class CanonicalCache(Protocol):
    """Protocol for canonical name cache interface."""

    def get_canonical_name(self, key: str) -> str | None:
        """Retrieve canonical name for a cache key."""
        ...

    def set_canonical_name(self, key: str, canonical: str) -> None:
        """Store canonical name mapping."""
        ...


class IdentityCanonicalizer:
    """Applies canonical identity mappings during metadata processing.

    Provides canonicalization of names during runtime (canonicalize, canonicalize_multi).
    """

    def __init__(self, cache: CanonicalCache) -> None:
        """Initialize the canonicalizer.

        Args:
            cache: Cache implementation for storing/retrieving canonical names
        """
        self.cache = cache
        self._local_cache: dict[str, str] = {}

    def canonicalize(self, name: str, category: str = "artist") -> str:
        """Get the canonical form of a name.

        Args:
            name: The name to canonicalize
            category: One of 'artist', 'composer', 'album_artist', 'conductor', 'performer'

        Returns:
            The canonical form, or the original name if no mapping exists
        """
        if not name:
            return name

        # Strip whitespace
        name = name.strip()

        token = normalize_token(name)
        if not token:
            return name

        cache_key = f"{category}::{token}"

        # Check local cache first
        if cache_key in self._local_cache:
            return self._local_cache[cache_key]

        # Check persistent cache
        canonical = self.cache.get_canonical_name(cache_key)
        if canonical:
            self._local_cache[cache_key] = canonical
            return canonical

        return name

    def canonicalize_multi(
        self, names: str, category: str = "artist", library_roots: list[Path] | None = None
    ) -> str:
        """Canonicalize a potentially multi-name string.

        Args:
            names: String containing one or more names (possibly comma or semicolon separated)
            category: Identity category (artist, composer, etc.)
            library_roots: Optional library roots (not used in simplified version)

        Returns:
            Canonicalized names separated by "; " (NOT commas)
        """
        if not names:
            return names

        # Split on common separators
        parts = []
        for sep in [";", ","]:
            if sep in names:
                parts = [p.strip() for p in names.split(sep) if p.strip()]
                break

        if not parts:
            parts = [names.strip()]

        canonical_parts = []
        seen = set()

        for part in parts:
            if part:
                canonical = self.canonicalize(part, category)
                # Avoid duplicates
                canonical_lower = canonical.lower()
                if canonical_lower not in seen:
                    canonical_parts.append(canonical)
                    seen.add(canonical_lower)

        # Always use semicolon as separator (NEVER comma)
        return "; ".join(canonical_parts) if canonical_parts else names
