"""Load and validate serialized Plan/TagPatch artifacts."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from resonance.core.enricher import AlbumTagPatch, TagPatch, TrackTagPatch
from resonance.core.planner import Plan, TrackOperation
from resonance.core.validation import SafePath, validate_dir_id, validate_release_id, validate_signature_hash


def _require(value: Any, name: str) -> Any:
    if value is None:
        raise ValueError(f"Missing required field: {name}")
    return value


def _ensure_int(value: Any, name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"Invalid {name}: expected int")
    return value


def _ensure_str(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Invalid {name}: expected str")
    return value


def _resolve_destination_path(path: Path, allowed_roots: tuple[Path, ...]) -> Path:
    if path.is_absolute():
        return path
    if len(allowed_roots) != 1:
        raise ValueError("Relative destination path requires a single allowed_root")
    return allowed_roots[0] / path


def load_plan(path: Path, *, allowed_roots: tuple[Path, ...]) -> Plan:
    data = json.loads(path.read_text())
    dir_id = _ensure_str(_require(data.get("dir_id"), "dir_id"), "dir_id")
    validate_dir_id(dir_id)
    signature_hash = _ensure_str(
        _require(data.get("signature_hash"), "signature_hash"),
        "signature_hash",
    )
    validate_signature_hash(signature_hash)
    release_id = _ensure_str(_require(data.get("release_id"), "release_id"), "release_id")
    validate_release_id(release_id)
    source_path = Path(_ensure_str(_require(data.get("source_path"), "source_path"), "source_path"))
    if not source_path.is_absolute():
        raise ValueError("Plan source_path must be absolute")
    SafePath(source_path, (source_path,))

    raw_ops = _require(data.get("operations"), "operations")
    if not isinstance(raw_ops, list):
        raise ValueError("Invalid operations: expected list")

    operations: list[TrackOperation] = []
    for raw_op in raw_ops:
        if not isinstance(raw_op, dict):
            raise ValueError("Invalid operation entry")
        track_position = _ensure_int(
            _require(raw_op.get("track_position"), "track_position"),
            "track_position",
        )
        src = Path(_ensure_str(_require(raw_op.get("source_path"), "source_path"), "source_path"))
        dest = Path(_ensure_str(_require(raw_op.get("destination_path"), "destination_path"), "destination_path"))
        src = source_path / src if not src.is_absolute() else src
        dest = _resolve_destination_path(dest, allowed_roots)
        SafePath(src, (source_path,))
        SafePath(dest, allowed_roots)
        operations.append(
            TrackOperation(
                track_position=track_position,
                source_path=src,
                destination_path=dest,
                track_title=_ensure_str(_require(raw_op.get("track_title"), "track_title"), "track_title"),
            )
        )

    plan = Plan(
        dir_id=dir_id,
        source_path=source_path,
        signature_hash=signature_hash,
        provider=_ensure_str(_require(data.get("provider"), "provider"), "provider"),
        release_id=release_id,
        release_title=_ensure_str(_require(data.get("release_title"), "release_title"), "release_title"),
        release_artist=_ensure_str(_require(data.get("release_artist"), "release_artist"), "release_artist"),
        destination_path=_resolve_destination_path(
            Path(_ensure_str(_require(data.get("destination_path"), "destination_path"), "destination_path")),
            allowed_roots,
        ),
        operations=tuple(operations),
        non_audio_policy=_ensure_str(_require(data.get("non_audio_policy"), "non_audio_policy"), "non_audio_policy"),
        plan_version=_ensure_str(_require(data.get("plan_version"), "plan_version"), "plan_version"),
        is_compilation=bool(data.get("is_compilation", False)),
        compilation_reason=data.get("compilation_reason"),
        is_classical=bool(data.get("is_classical", False)),
        conflict_policy=_ensure_str(_require(data.get("conflict_policy"), "conflict_policy"), "conflict_policy"),
        settings_hash=data.get("settings_hash"),
    )
    return plan


def load_tag_patch(path: Path) -> TagPatch:
    data = json.loads(path.read_text())
    dir_id = _ensure_str(_require(data.get("dir_id"), "dir_id"), "dir_id")
    validate_dir_id(dir_id)
    release_id = _ensure_str(_require(data.get("release_id"), "release_id"), "release_id")
    validate_release_id(release_id)

    album_patch = None
    raw_album = data.get("album_patch")
    if raw_album is not None:
        if not isinstance(raw_album, dict):
            raise ValueError("Invalid album_patch: expected dict")
        album_patch = AlbumTagPatch(set_tags=dict(raw_album.get("set_tags", {})))

    raw_tracks = _require(data.get("track_patches"), "track_patches")
    if not isinstance(raw_tracks, list):
        raise ValueError("Invalid track_patches: expected list")
    track_patches: list[TrackTagPatch] = []
    for raw_track in raw_tracks:
        if not isinstance(raw_track, dict):
            raise ValueError("Invalid track_patch entry")
        track_patches.append(
            TrackTagPatch(
                track_position=_ensure_int(
                    _require(raw_track.get("track_position"), "track_position"),
                    "track_position",
                ),
                set_tags=dict(raw_track.get("set_tags", {})),
            )
        )

    return TagPatch(
        dir_id=dir_id,
        provider=_ensure_str(_require(data.get("provider"), "provider"), "provider"),
        release_id=release_id,
        version=_ensure_str(_require(data.get("version"), "version"), "version"),
        allowed=bool(data.get("allowed", False)),
        reason=data.get("reason"),
        album_patch=album_patch,
        track_patches=tuple(track_patches),
        provenance_tags=dict(data.get("provenance_tags", {})),
        allow_overwrite=bool(data.get("allow_overwrite", False)),
        overwrite_fields=tuple(data.get("overwrite_fields", ())),
    )


def serialize_plan(plan: Plan) -> str:
    payload = asdict(plan)
    payload = _convert_paths(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _convert_paths(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {key: _convert_paths(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_convert_paths(item) for item in obj]
    return obj
