"""Identity canonicalization system for Resonance.

This module provides canonical name resolution for artists, composers, and performers.
"""

from .canonicalizer import IdentityCanonicalizer, CanonicalCache

__all__ = [
    "IdentityCanonicalizer",
    "CanonicalCache",
]
