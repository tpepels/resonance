"""Enricher - deterministic tag patch generation from pinned releases.

This module generates pure, deterministic TagPatch artifacts without I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from resonance.core.identifier import ProviderRelease
from resonance.core.planner import Plan
from resonance.core.state import DirectoryState

TAGPATCH_VERSION = "v1"


@dataclass(frozen=True)
class AlbumTagPatch:
    """Album-level tag diff."""

    set_tags: dict[str, str]
    unset_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class TrackTagPatch:
    """Per-track tag diff."""

    track_position: int
    set_tags: dict[str, str]
    unset_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class TagPatch:
    """Deterministic tag patch artifact."""

    version: str
    dir_id: str
    provider: str
    release_id: str
    allowed: bool
    reason: Optional[str]
    allow_overwrite: bool
    album_patch: Optional[AlbumTagPatch]
    track_patches: tuple[TrackTagPatch, ...]


def _empty_patch(
    plan: Plan,
    release: ProviderRelease,
    *,
    allow_overwrite: bool,
    reason: str,
) -> TagPatch:
    return TagPatch(
        version=TAGPATCH_VERSION,
        dir_id=plan.dir_id,
        provider=release.provider,
        release_id=release.release_id,
        allowed=False,
        reason=reason,
        allow_overwrite=allow_overwrite,
        album_patch=None,
        track_patches=(),
    )


def build_tag_patch(
    plan: Plan,
    pinned_release: ProviderRelease,
    resolution_state: DirectoryState,
    *,
    allow_user_resolved: bool = False,
    allow_overwrite: bool = False,
) -> TagPatch:
    """Build a deterministic tag patch from a plan and pinned release."""
    if resolution_state not in (
        DirectoryState.RESOLVED_AUTO,
        DirectoryState.RESOLVED_USER,
    ):
        return _empty_patch(
            plan,
            pinned_release,
            allow_overwrite=allow_overwrite,
            reason="state_not_resolved",
        )

    if resolution_state == DirectoryState.RESOLVED_USER and not allow_user_resolved:
        return _empty_patch(
            plan,
            pinned_release,
            allow_overwrite=allow_overwrite,
            reason="user_resolved_not_allowed",
        )

    album_patch = AlbumTagPatch(
        set_tags={
            "album": pinned_release.title,
            "albumartist": pinned_release.artist,
        },
        unset_tags=(),
    )

    track_by_position = {track.position: track for track in pinned_release.tracks}
    ordered_ops = sorted(plan.operations, key=lambda op: op.track_position)
    missing = [
        op.track_position for op in ordered_ops if op.track_position not in track_by_position
    ]
    if missing:
        raise ValueError(f"Cannot build tag patch: missing tracks for positions {missing}")

    track_patches = tuple(
        TrackTagPatch(
            track_position=op.track_position,
            set_tags={
                "title": track_by_position[op.track_position].title,
                "tracknumber": str(op.track_position),
            },
            unset_tags=(),
        )
        for op in ordered_ops
    )

    return TagPatch(
        version=TAGPATCH_VERSION,
        dir_id=plan.dir_id,
        provider=pinned_release.provider,
        release_id=pinned_release.release_id,
        allowed=True,
        reason=None,
        allow_overwrite=allow_overwrite,
        album_patch=album_patch,
        track_patches=track_patches,
    )
