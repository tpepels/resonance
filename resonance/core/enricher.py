"""Enricher - deterministic tag patch generation from pinned releases.

This module generates pure, deterministic TagPatch artifacts without I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Optional

from resonance.core.identifier import ProviderRelease
from resonance.core.planner import Plan
from resonance.core.state import DirectoryState
from resonance import __version__

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
    overwrite_fields: tuple[str, ...]
    provenance_tags: dict[str, str]
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
        overwrite_fields=(),
        provenance_tags={},
        album_patch=None,
        track_patches=(),
    )


def _stable_plan_hash(plan: Plan) -> str:
    payload = asdict(plan)

    def convert_paths(obj):
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {k: convert_paths(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [convert_paths(item) for item in obj]
        return obj

    payload = convert_paths(payload)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _provenance_tags(
    plan: Plan,
    release: ProviderRelease,
    now_fn,
) -> dict[str, str]:
    now = now_fn()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    timestamp = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "resonance.prov.version": "1",
        "resonance.prov.tool": "resonance",
        "resonance.prov.tool_version": __version__,
        "resonance.prov.dir_id": plan.dir_id,
        "resonance.prov.plan_hash": _stable_plan_hash(plan),
        "resonance.prov.pinned_provider": release.provider,
        "resonance.prov.pinned_release_id": release.release_id,
        "resonance.prov.applied_at_utc": timestamp,
    }


def build_tag_patch(
    plan: Plan,
    pinned_release: ProviderRelease,
    resolution_state: DirectoryState,
    *,
    allow_user_resolved: bool = False,
    allow_overwrite: bool = False,
    overwrite_fields: tuple[str, ...] = (),
    now_fn=lambda: datetime.now(timezone.utc),
) -> TagPatch:
    """Build a deterministic tag patch from a plan and pinned release.

    Note: behavior is deterministic but state-conditional; resolution_state gates
    whether tags are emitted (e.g., RESOLVED_USER may be suppressed unless allowed).
    """
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

    album_tags = {
        "album": pinned_release.title,
        "albumartist": pinned_release.artist,
    }
    if pinned_release.provider == "musicbrainz":
        album_tags["musicbrainz_albumid"] = pinned_release.release_id

    album_patch = AlbumTagPatch(
        set_tags=album_tags,
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
                **(
                    {"musicbrainz_recordingid": track_by_position[op.track_position].recording_id}
                    if track_by_position[op.track_position].recording_id
                    else {}
                ),
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
        overwrite_fields=overwrite_fields,
        provenance_tags=_provenance_tags(plan, pinned_release, now_fn),
        album_patch=album_patch,
        track_patches=track_patches,
    )
