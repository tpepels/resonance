"""Directory signature helpers for stable identity."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Any


@dataclass(frozen=True)
class AudioFileSignature:
    """Stable signature data for a single audio file."""
    fingerprint_id: str | None
    duration_seconds: int | None
    size_bytes: int

    def sort_key(self) -> tuple[Any, ...]:
        """Return a stable sort key for deterministic ordering."""
        return (
            self.fingerprint_id or "",
            self.duration_seconds or 0,
            self.size_bytes,
        )


@dataclass(frozen=True)
class DirectorySignature:
    """Stable directory signature computed from audio files."""
    audio_files: tuple[AudioFileSignature, ...]
    signature_hash: str
    signature_version: int = 1
    non_audio_files: tuple[str, ...] = ()


def dir_signature(
    audio_files: Iterable[Path],
    non_audio_files: Iterable[Path] | None = None,
) -> DirectorySignature:
    """Compute a deterministic directory signature from audio files.

    CRITICAL: The signature_hash (used for dir_id) is based ONLY on:
    - fingerprint_id (content identity)
    - duration_seconds (content identity)

    It explicitly EXCLUDES size_bytes to ensure identity stability when:
    - Tags are written (changes file size)
    - Files are moved (doesn't change content)

    This implements the Phase A.2 invariant: "once resolved, never re-matched
    unless content changes."
    """
    signatures = [file_signature(path) for path in audio_files]
    signatures.sort(key=lambda item: item.sort_key())

    # Identity payload: ONLY content-based fields, NO size_bytes
    payload = [
        {
            "fingerprint_id": sig.fingerprint_id,
            "duration_seconds": sig.duration_seconds,
            # size_bytes deliberately excluded - changes when tags written
        }
        for sig in signatures
    ]

    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    non_audio_entries = tuple(
        sorted(path.as_posix() for path in (non_audio_files or []))
    )

    return DirectorySignature(
        audio_files=tuple(signatures),
        signature_hash=signature_hash,
        signature_version=1,
        non_audio_files=non_audio_entries,
    )


def dir_id(signature: DirectorySignature) -> str:
    """Return the stable directory id derived from a signature."""
    return signature.signature_hash


def file_signature(path: Path) -> AudioFileSignature:
    """Compute a stable audio file signature from file metadata."""
    metadata = _read_stub_metadata(path)
    fingerprint_id = _safe_get(metadata, "fingerprint_id")
    duration_seconds = _safe_get(metadata, "duration_seconds")

    try:
        size_bytes = path.stat().st_size
    except FileNotFoundError:
        size_bytes = 0

    return AudioFileSignature(
        fingerprint_id=fingerprint_id if isinstance(fingerprint_id, str) else None,
        duration_seconds=int(duration_seconds) if isinstance(duration_seconds, int) else None,
        size_bytes=size_bytes,
    )


def _read_stub_metadata(path: Path) -> dict[str, Any]:
    """Read optional stub metadata saved alongside test fixtures."""
    metadata_path = path.with_suffix(path.suffix + ".meta.json")
    if not metadata_path.exists():
        return {}

    try:
        return json.loads(metadata_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _safe_get(data: dict[str, Any], key: str) -> Any:
    """Return a value from dict without raising KeyError."""
    return data.get(key)
