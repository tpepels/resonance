"""Shared sidecar metadata reader for .meta.json files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def path_hash(path: Path, length: int = 16) -> str:
    """Stable hash of a file path for sidecar naming."""
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:length]


def stable_hash(obj: Any) -> str:
    """SHA-256 hex digest of a deterministically serialized object.

    Uses ``json.dumps`` with sorted keys and compact separators so that
    structurally identical objects always produce the same hash.
    """
    serialized = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def read_sidecar(path: Path, *, hash_first: bool = True) -> dict[str, Any]:
    """Read .meta.json sidecar for an audio file.

    Tries two naming schemes:
    - Hash-based: ``<sha256(path)[:16]>.meta.json`` (handles long filenames)
    - Suffix-based: ``<file>.ext.meta.json`` (legacy test stubs)

    Args:
        path: Path to the audio file.
        hash_first: If True, try hash-based path first (default). Set False
            for suffix-first lookup.

    Returns:
        Parsed sidecar dict, or empty dict if not found or unreadable.
    """
    h = path_hash(path)
    hash_path = path.parent / f"{h}.meta.json"
    suffix_path = path.with_suffix(path.suffix + ".meta.json")

    candidates = (hash_path, suffix_path) if hash_first else (suffix_path, hash_path)

    for meta_path in candidates:
        try:
            if meta_path.exists():
                return json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
    return {}
