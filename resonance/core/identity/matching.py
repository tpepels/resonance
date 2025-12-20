"""Name normalization for identity canonicalization.

This module provides token normalization for matching name variants.
"""

from __future__ import annotations

import re
import unicodedata


# Feature patterns to remove during normalization
FEAT_PATTERNS = [
    r'\s*\(?\s*feat\.?\s+[^)]+\)?',
    r'\s*\(?\s*featuring\s+[^)]+\)?',
    r'\s*\(?\s*ft\.?\s+[^)]+\)?',
    r'\s*\(?\s*with\s+[^)]+\)?',
]


def normalize_token(value: str) -> str:
    """Normalize a name to a token for clustering.

    This creates a unique identifier while preserving enough information
    to distinguish different people.

    Process:
    1. Remove featuring patterns
    2. Unicode normalization (NFKD)
    3. Convert to ASCII
    4. Lowercase
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

    # Remove featuring patterns first
    cleaned = value
    for pattern in FEAT_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Unicode normalization
    normalized = unicodedata.normalize("NFKD", cleaned)

    # Convert to ASCII
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")

    # Lowercase
    ascii_only = ascii_only.lower()

    # Remove punctuation but keep spaces temporarily
    ascii_only = re.sub(r"[^a-z0-9\s]+", " ", ascii_only)

    # Collapse multiple spaces
    ascii_only = re.sub(r"\s+", " ", ascii_only).strip()

    # Remove spaces for final token (but we kept them to preserve word boundaries)
    token = ascii_only.replace(" ", "")

    return token if token else ""
