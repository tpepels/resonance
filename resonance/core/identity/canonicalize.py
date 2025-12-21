"""Pure canonicalization functions for artist/album/work names.

This module provides the authoritative canonicalization layer with two
distinct purposes:

1. **Display canonicalization** (`display_*`):
   - Preserves diacritics and proper casing
   - Used for human-readable output (tags, paths, UI)
   - Example: "Björk" stays "Björk"

2. **Match key canonicalization** (`match_key_*`):
   - Aggressive normalization for matching/caching
   - Strips diacritics, removes punctuation, lowercases
   - Used for deduplication and equivalence checks
   - Example: "Björk" → "bjork"

All functions are pure (no side effects, no cache access).
Persistence of learned canonical mappings lives in DirectoryStateStore.

See: TDD_TODO_V3.md Phase A.1, CONSOLIDATED_AUDIT.md §C-1
"""

from __future__ import annotations

import re
import unicodedata


# Patterns for normalization
_JOINER_PATTERN = re.compile(
    r"\s*(?:&|\band\b|/|;|\bx\b|×)\s*",
    flags=re.IGNORECASE,
)

_FEAT_PATTERN = re.compile(
    r"\s*(?:\(|\[)?\s*\b(feat|featuring|ft|including)\b\.?\s*[^)\]]*\)?",
    flags=re.IGNORECASE,
)


# ============================================================================
# Display Canonicalization (Human-Readable)
# ============================================================================


def display_artist(name: str) -> str:
    """Canonicalize artist name for display (preserves diacritics).

    Args:
        name: Raw artist name from metadata

    Returns:
        Display-ready artist name with proper spacing and Unicode preserved

    Examples:
        >>> display_artist("  Björk  ")
        'Björk'
        >>> display_artist("The Beatles")
        'The Beatles'
    """
    if not name:
        return name

    # Unicode normalization (NFKC preserves diacritics)
    cleaned = unicodedata.normalize("NFKC", name).strip()

    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned


def display_album(title: str) -> str:
    """Canonicalize album title for display (preserves diacritics).

    Args:
        title: Raw album title from metadata

    Returns:
        Display-ready album title

    Examples:
        >>> display_album("  Homogenic  ")
        'Homogenic'
    """
    if not title:
        return title

    cleaned = unicodedata.normalize("NFKC", title).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned


def display_work(title: str) -> str:
    """Canonicalize work/composition title for display (preserves diacritics).

    Args:
        title: Raw work title from metadata

    Returns:
        Display-ready work title

    Examples:
        >>> display_work("Piano Sonata No. 14 in C♯ minor")
        'Piano Sonata No. 14 in C♯ minor'
    """
    if not title:
        return title

    cleaned = unicodedata.normalize("NFKC", title).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned


# ============================================================================
# Match Key Canonicalization (Aggressive Equivalence)
# ============================================================================


def match_key_artist(name: str) -> str:
    """Create aggressive match key for artist deduplication.

    This removes diacritics, punctuation, and casing to enable broad matching.
    Used for cache lookups and equivalence checks, NOT for display.

    Args:
        name: Artist name to create match key for

    Returns:
        Normalized match key (lowercase, ASCII-only, no spaces)

    Examples:
        >>> match_key_artist("Björk")
        'bjork'
        >>> match_key_artist("AC/DC")
        'acdc'
        >>> match_key_artist("The Beatles")
        'thebeatles'
        >>> match_key_artist("Yo-Yo Ma")
        'yoyoma'
    """
    if not name:
        return ""

    # Unicode normalization and whitespace cleanup
    cleaned = unicodedata.normalize("NFKC", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Remove featuring segments
    cleaned = _FEAT_PATTERN.sub("", cleaned)

    # Normalize joiners to spaces
    cleaned = _JOINER_PATTERN.sub(" ", cleaned)

    # Casefold for stable comparison
    cleaned = cleaned.casefold()

    # Fold diacritics to ASCII-equivalent characters
    # NFKD separates base chars from diacritics, then we filter out combining marks
    normalized = unicodedata.normalize("NFKD", cleaned)
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))

    # Remove punctuation but keep spaces temporarily (for word boundaries)
    ascii_only = re.sub(r"[^a-z0-9\s]+", " ", ascii_only)

    # Collapse multiple spaces
    ascii_only = re.sub(r"\s+", " ", ascii_only).strip()

    # Remove spaces for final token
    token = ascii_only.replace(" ", "")

    return token


def match_key_album(title: str) -> str:
    """Create aggressive match key for album deduplication.

    Args:
        title: Album title to create match key for

    Returns:
        Normalized match key

    Examples:
        >>> match_key_album("Homogenic")
        'homogenic'
        >>> match_key_album("The Best of Björk")
        'thebestofbjork'
    """
    # For now, albums use the same normalization as artists
    return match_key_artist(title)


def match_key_work(title: str) -> str:
    """Create aggressive match key for work/composition deduplication.

    Args:
        title: Work title to create match key for

    Returns:
        Normalized match key

    Examples:
        >>> match_key_work("Piano Sonata No. 14")
        'pianosonatano14'
    """
    # For now, works use the same normalization as artists
    return match_key_artist(title)


# ============================================================================
# Multi-Name Handling
# ============================================================================


def split_names(value: str) -> list[str]:
    """Split a multi-name string into deterministic parts.

    Handles various separators: commas, semicolons, "feat.", "&", etc.

    Args:
        value: Multi-name string (e.g., "Artist A feat. Artist B")

    Returns:
        List of individual names

    Examples:
        >>> split_names("Art Blakey & The Jazz Messengers")
        ['Art Blakey', 'The Jazz Messengers']
        >>> split_names("Artist feat. Guest")
        ['Artist', 'Guest']
    """
    if not value:
        return []

    cleaned = unicodedata.normalize("NFKC", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Convert featuring keywords to semicolons (BEFORE general joiner normalization)
    cleaned = re.sub(r"\bfeat\.?\b", ";", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bfeaturing\b", ";", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bft\.?\b", ";", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bincluding\b", ";", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bwith\b", ";", cleaned, flags=re.IGNORECASE)
    # Handle "w/" specially before general "/" processing
    cleaned = re.sub(r"\bw/\s+", "; ", cleaned, flags=re.IGNORECASE)

    # Normalize joiners to semicolons
    cleaned = _JOINER_PATTERN.sub(";", cleaned)

    # Consolidate separators
    cleaned = re.sub(r"[,&;]+", ";", cleaned)  # Removed "/" from here since it's in JOINER_PATTERN

    # Split and clean
    parts = []
    for part in cleaned.split(";"):
        part = part.strip()
        # Remove leading/trailing non-word characters
        part = re.sub(r"^[\W_]+|[\W_]+$", "", part)
        if part:
            parts.append(part)

    return parts


def dedupe_names(names: list[str]) -> list[str]:
    """Remove duplicate names using match key comparison.

    Args:
        names: List of names (possibly with duplicates)

    Returns:
        Deduplicated list preserving first occurrence

    Examples:
        >>> dedupe_names(["Björk", "Bjork", "björk"])
        ['Björk']
    """
    seen: set[str] = set()
    unique: list[str] = []

    for name in names:
        key = match_key_artist(name)
        if key and key not in seen:
            unique.append(name)
            seen.add(key)

    return unique
