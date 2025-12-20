"""Name normalization for identity canonicalization.

This module provides token normalization for matching name variants.
"""

from __future__ import annotations

import re
import unicodedata


JOINER_PATTERN = re.compile(
    r"\s*(?:&|\band\b|/|;|\bx\b|×)\s*",
    flags=re.IGNORECASE,
)

SHORT_NAME_SEPARATOR = re.compile(r"\s+-\s+|\s+–\s+|\s+—\s+|\s*:\s*|\s*/\s*|\s*;\s*|\s*\|\s*")

FEAT_SEGMENT_PATTERN = re.compile(
    r"\s*(?:\(|\[)?\s*\b(feat|featuring|ft|including)\b\.?\s*[^)\]]*\)?",
    flags=re.IGNORECASE,
)


def normalize_token(value: str | None) -> str:
    """Normalize a name to a token for clustering.

    This creates a unique identifier while preserving enough information
    to distinguish different people.

    Process:
    1. Remove featuring patterns
    2. Unicode normalization (NFKC)
    3. Casefold for stable comparisons
    4. Normalize joiners (&/and/;/x) as separators
    5. Remove punctuation (keep spaces temporarily)
    6. Collapse spaces
    7. Remove all spaces for final token

    Examples:
        "Ludwig van Beethoven" → "ludwigvonbeethoven"
        "Art Blakey & The Jazz Messengers" → "artblakeythejazzmessengers"
        "Yo-Yo Ma" → "yoyoma"

    Args:
        value: The name to normalize

    Returns:
        Normalized token (alphanumeric, lowercase, no spaces)
    """
    if not value:
        return ""

    # Unicode normalization and whitespace cleanup
    cleaned = unicodedata.normalize("NFKC", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Remove featuring segments
    cleaned = FEAT_SEGMENT_PATTERN.sub("", cleaned)

    # Normalize joiners to spaces
    cleaned = JOINER_PATTERN.sub(" ", cleaned)

    # Casefold for stable comparison
    cleaned = cleaned.casefold()

    # Fold diacritics to ASCII-equivalent characters
    normalized = unicodedata.normalize("NFKD", cleaned)
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))

    # Remove punctuation but keep spaces temporarily
    ascii_only = re.sub(r"[^a-z0-9\s]+", " ", ascii_only)

    # Collapse multiple spaces
    ascii_only = re.sub(r"\s+", " ", ascii_only).strip()

    # Remove spaces for final token (but we kept them to preserve word boundaries)
    token = ascii_only.replace(" ", "")

    return token if token else ""


def split_names(value: str | None) -> list[str]:
    """Split a multi-name string into deterministic parts."""
    if not value:
        return []

    cleaned = unicodedata.normalize("NFKC", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    cleaned = re.sub(r"\bfeat\.?\b", ";", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bfeaturing\b", ";", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bft\.?\b", ";", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bincluding\b", ";", cleaned, flags=re.IGNORECASE)
    cleaned = JOINER_PATTERN.sub(";", cleaned)
    cleaned = re.sub(r"[,&/;]+", ";", cleaned)

    parts = []
    for part in cleaned.split(";"):
        part = part.strip()
        part = re.sub(r"^[\W_]+|[\W_]+$", "", part)
        if part:
            parts.append(part)
    return parts


def dedupe_names(names: list[str]) -> list[str]:
    """Remove duplicate names using normalized token comparison."""
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        token = normalize_token(name)
        if token and token not in seen:
            unique.append(name)
            seen.add(token)
    return unique


def strip_featuring(value: str | None) -> str | None:
    """Remove featuring segments from a display name without other normalization."""
    if not value:
        return value

    cleaned = unicodedata.normalize("NFKC", value).strip()
    cleaned = FEAT_SEGMENT_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def short_folder_name(value: str, max_length: int = 60) -> str:
    """Return a deterministic folder-safe name within the max length."""
    cleaned = value.strip()
    cleaned = FEAT_SEGMENT_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    # Clean up any unmatched brackets left over from featuring removal
    cleaned = re.sub(r"[\[\]]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) <= max_length:
        return cleaned

    clauses = [part.strip() for part in SHORT_NAME_SEPARATOR.split(cleaned) if part.strip()]
    if len(clauses) > 1:
        for end in range(len(clauses), 0, -1):
            candidate = " - ".join(clauses[:end]).strip()
            if len(candidate) <= max_length:
                return candidate
        cleaned = clauses[0]

    if len(cleaned) <= max_length:
        return cleaned

    primary = cleaned.split()[0] if cleaned.split() else cleaned
    if len(primary) <= max_length:
        return primary
    return primary[:max_length]
