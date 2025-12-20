"""Identity canonicalization system for Resonance.

This module provides canonical name resolution for artists, composers, and performers.
"""

from .canonicalizer import IdentityCanonicalizer, CanonicalCache
from .signature import DirectorySignature, AudioFileSignature, dir_signature, dir_id, file_signature

__all__ = [
    "IdentityCanonicalizer",
    "CanonicalCache",
    "DirectorySignature",
    "AudioFileSignature",
    "dir_signature",
    "dir_id",
    "file_signature",
]
