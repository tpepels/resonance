"""Identity canonicalization system for Resonance.

This module provides canonical name resolution for artists, composers, and performers.

The canonicalization system has two distinct layers:
- Display canonicalization: Preserves diacritics for human-readable output
- Match key canonicalization: Aggressive normalization for equivalence checks

See: resonance.core.identity.canonicalize for the pure function API
See: TDD_TODO_V3.md Phase A.1 for design rationale
"""

from .canonicalizer import IdentityCanonicalizer, CanonicalCache
from .signature import DirectorySignature, AudioFileSignature, dir_signature, dir_id, file_signature
from .canonicalize import (
    # Display functions (preserve Unicode)
    display_artist,
    display_album,
    display_work,
    # Match key functions (aggressive normalization)
    match_key_artist,
    match_key_album,
    match_key_work,
    # Utilities
    split_names,
    dedupe_names,
)

__all__ = [
    # Legacy class-based API
    "IdentityCanonicalizer",
    "CanonicalCache",
    # Signature API
    "DirectorySignature",
    "AudioFileSignature",
    "dir_signature",
    "dir_id",
    "file_signature",
    # Pure canonicalization functions (NEW - Phase A.1)
    "display_artist",
    "display_album",
    "display_work",
    "match_key_artist",
    "match_key_album",
    "match_key_work",
    "split_names",
    "dedupe_names",
]
