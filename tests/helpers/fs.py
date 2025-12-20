"""Filesystem scaffolding helpers for tests."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AudioStubSpec:
    """Specification for an audio stub file."""
    filename: str
    fingerprint_id: str
    duration_seconds: int = 180
    size_bytes: int = 2048
    tags: dict[str, Any] | None = None


@dataclass(frozen=True)
class AlbumFixture:
    """Represents a created album fixture on disk."""
    name: str
    path: Path
    audio_files: list[Path]
    non_audio_files: list[Path]
    audio_specs: list[AudioStubSpec]


def create_audio_stub(path: Path, spec: AudioStubSpec) -> Path:
    """Create an audio stub file with deterministic content and metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)

    header = f"FP:{spec.fingerprint_id}\nDURATION:{spec.duration_seconds}\n"
    content = header.encode("ascii", errors="ignore")
    if spec.size_bytes <= 0:
        data = content
    elif len(content) >= spec.size_bytes:
        data = content[:spec.size_bytes]
    else:
        padding = b"\0" * (spec.size_bytes - len(content))
        data = content + padding

    path.write_bytes(data)

    metadata_path = path.with_suffix(path.suffix + ".meta.json")
    metadata = {
        "fingerprint_id": spec.fingerprint_id,
        "duration_seconds": spec.duration_seconds,
        "size_bytes": spec.size_bytes,
        "tags": spec.tags or {},
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))

    return path


def create_non_audio_stub(path: Path) -> Path:
    """Create a non-audio stub file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub")
    return path


def build_album_dir(
    base_dir: Path,
    name: str,
    audio_specs: list[AudioStubSpec],
    non_audio_files: list[str] | None = None,
) -> AlbumFixture:
    """Create an album directory with audio and non-audio stubs."""
    album_dir = base_dir / name
    album_dir.mkdir(parents=True, exist_ok=True)

    audio_files: list[Path] = []
    for spec in audio_specs:
        audio_path = album_dir / spec.filename
        audio_files.append(create_audio_stub(audio_path, spec))

    non_audio_paths: list[Path] = []
    for filename in non_audio_files or []:
        non_audio_paths.append(create_non_audio_stub(album_dir / filename))

    return AlbumFixture(
        name=name,
        path=album_dir,
        audio_files=audio_files,
        non_audio_files=non_audio_paths,
        audio_specs=audio_specs,
    )
