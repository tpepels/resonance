"""Planner - deterministic plan generation from pinned releases.

This module generates reproducible Plan artifacts that specify exactly how
to organize a directory. Plans are pure (no I/O) and deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from resonance.core.identifier import ProviderRelease
from resonance.core.state import DirectoryState
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
    conflict_policy: str = "FAIL"


def sanitize_filename(name: str) -> str:
    """Deterministically sanitize a filename for cross-platform safety."""
    forbidden = '<>:"/\\|?*'
    cleaned = []
    for ch in name:
        if ch in forbidden:
            cleaned.append(" ")
        else:
            cleaned.append(ch)
    collapsed = " ".join("".join(cleaned).split())
    if not collapsed:
        collapsed = "_"
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    if collapsed.upper() in reserved:
        return f"_{collapsed}"
    return collapsed


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


def _classical_composer(release: ProviderRelease) -> str | None:
    composers = []
    for track in release.tracks:
        composer = getattr(track, "composer", None)
        if composer:
            composers.append(composer)
    unique = sorted({composer.strip() for composer in composers if composer.strip()})
    if len(unique) == 1:
        return unique[0]
    return None


def _is_classical(release: ProviderRelease) -> bool:
    composers = []
    for track in release.tracks:
        composer = getattr(track, "composer", None)
        if composer:
            composers.append(composer)
    return len({composer.strip() for composer in composers if composer.strip()}) > 0


def _compute_destination_path(
    release: ProviderRelease,
    is_compilation: bool,
    is_classical: bool,
    canonicalize_display,
) -> Path:
    """Compute destination path based on release type."""
    def display(value: str, category: str) -> str:
        return canonicalize_display(value, category)

    if is_compilation:
        # Compilation: Various Artists/Album
        return Path("Various Artists") / release.title

    if is_classical:
        composer = _classical_composer(release)
        if composer:
            return Path(display(composer, "composer")) / release.title
        return Path(display(release.artist, "performer")) / release.title

    # Regular album: Artist/Album
    return Path(display(release.artist, "artist")) / release.title


def plan_directory(
    dir_id: str,
    store: DirectoryStateStore,
    pinned_release: ProviderRelease,
    non_audio_policy: str = "MOVE_WITH_ALBUM",
    canonicalize_display=None,
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

    # Detect compilation/classical
    compilation_reason = _compilation_reason(pinned_release)
    is_compilation = compilation_reason is not None
    is_classical = _is_classical(pinned_release)

    # Compute destination path
    if canonicalize_display is None:
        canonicalize_display = lambda value, _category: value

    destination_path = _compute_destination_path(
        pinned_release, is_compilation, is_classical, canonicalize_display
    )

    # Generate operations (placeholder - would need actual source file paths)
    # For now, just create deterministic ordering based on track positions
    operations = tuple(
        TrackOperation(
            track_position=track.position,
            source_path=Path(f"placeholder_{track.position}.flac"),
            destination_path=destination_path
            / f"{track.position:02d} - {sanitize_filename(track.title)}.flac",
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
        is_classical=is_classical,
        conflict_policy="FAIL",
    )
