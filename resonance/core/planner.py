"""Planner - deterministic plan generation from pinned releases.

This module generates reproducible Plan artifacts that specify exactly how
to organize a directory. Plans are pure (no I/O) and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from resonance.core.identifier import ProviderRelease, ProviderTrack
from resonance.core.state import DirectoryRecord, DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


class NonAudioPolicy(str, Enum):
    """Policy for handling non-audio files."""

    MOVE_WITH_ALBUM = "MOVE_WITH_ALBUM"  # Move with audio files (default)
    LEAVE_IN_PLACE = "LEAVE_IN_PLACE"    # Don't move non-audio
    DELETE = "DELETE"                     # Delete non-audio (requires explicit opt-in)


@dataclass(frozen=True)
class TrackOperation:
    """Single track move/rename operation."""

    track_position: int
    source_path: Path
    destination_path: Path
    track_title: str


@dataclass(frozen=True)
class Plan:
    """Deterministic plan for organizing a directory.

    This artifact specifies exactly what moves/renames to perform.
    It is serializable to JSON and byte-identical for identical inputs.
    """

    # Identity
    dir_id: str
    source_path: Path
    signature_hash: str

    # Pinned resolution
    provider: str
    release_id: str
    release_title: str
    release_artist: str

    # Destination
    destination_path: Path

    # Operations (ordered by track position)
    operations: tuple[TrackOperation, ...]

    # Policy
    non_audio_policy: str = "MOVE_WITH_ALBUM"

    # Metadata
    plan_version: str = "v1"
    is_compilation: bool = False
    compilation_reason: Optional[str] = None
    is_classical: bool = False


_COMPILATION_TOKENS = frozenset(
    {
        "various artists",
        "various artist",
        "various",
        "va",
    }
)


def _normalize_artist_token(artist: str) -> str:
    return " ".join(artist.strip().lower().replace(".", "").split())


def _compilation_reason(release: ProviderRelease) -> Optional[str]:
    """Return a stable reason if release is a compilation, otherwise None."""
    normalized = _normalize_artist_token(release.artist)
    if normalized in _COMPILATION_TOKENS:
        return "artist_in_compilation_allowlist"
    return None


def _compute_destination_path(release: ProviderRelease, is_compilation: bool) -> Path:
    """Compute destination path based on release type."""
    if is_compilation:
        # Compilation: Various Artists/Album
        return Path("Various Artists") / release.title

    # Regular album: Artist/Album
    return Path(release.artist) / release.title


def plan_directory(
    dir_id: str,
    store: DirectoryStateStore,
    pinned_release: ProviderRelease,
    non_audio_policy: str = "MOVE_WITH_ALBUM",
) -> Plan:
    """Generate a deterministic plan for a resolved directory.

    Args:
        dir_id: Directory identifier
        store: Directory state store
        pinned_release: Pinned provider release
        non_audio_policy: Policy for non-audio files

    Returns:
        Plan artifact

    Raises:
        ValueError: If directory is not in a plannable state (RESOLVED_*)
    """
    # Get directory record
    record = store.get(dir_id)
    if not record:
        raise ValueError(f"Directory {dir_id} not found in store")

    # Verify state is plannable
    if record.state not in (DirectoryState.RESOLVED_AUTO, DirectoryState.RESOLVED_USER):
        raise ValueError(
            f"Cannot plan directory in state {record.state.value}. "
            f"Only RESOLVED_AUTO and RESOLVED_USER can be planned."
        )

    # Detect compilation
    compilation_reason = _compilation_reason(pinned_release)
    is_compilation = compilation_reason is not None

    # Compute destination path
    destination_path = _compute_destination_path(pinned_release, is_compilation)

    # Generate operations (placeholder - would need actual source file paths)
    # For now, just create deterministic ordering based on track positions
    operations = tuple(
        TrackOperation(
            track_position=track.position,
            source_path=Path(f"placeholder_{track.position}.flac"),
            destination_path=destination_path / f"{track.position:02d} - {track.title}.flac",
            track_title=track.title,
        )
        for track in sorted(pinned_release.tracks, key=lambda t: t.position)
    )

    return Plan(
        dir_id=dir_id,
        source_path=record.last_seen_path,
        signature_hash=record.signature_hash,
        provider=pinned_release.provider,
        release_id=pinned_release.release_id,
        release_title=pinned_release.title,
        release_artist=pinned_release.artist,
        destination_path=destination_path,
        operations=operations,
        non_audio_policy=non_audio_policy,
        is_compilation=is_compilation,
        compilation_reason=compilation_reason,
        is_classical=False,  # TODO: Classical detection
    )
