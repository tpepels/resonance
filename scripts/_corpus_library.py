"""Shared helper: build a temporary library tree from metadata.json.

Creates real files and `.meta.json` sidecars so the standard Resonance
pipeline (scanner, signature, evidence extraction) works without
FakerContext monkey-patching.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def _parse_tags_from_path(relative_path: str) -> dict[str, str]:
    """Extract artist/album/year tags from the directory portion of a path.

    Handles two common patterns found in the real corpus:
      - "Artist/Album/track.flac"           → artist, album
      - "(YEAR) Artist - Album [FMT]/..."   → artist, album, date
      - "Artist - Album (YEAR) FMT/..."     → artist, album, date
    """
    dir_part = relative_path.rsplit("/", 1)[0] if "/" in relative_path else ""
    if not dir_part:
        return {}

    tags: dict[str, str] = {}

    parts = dir_part.split("/")
    if len(parts) >= 2:
        # Artist/Album structure
        tags["artist"] = parts[0]
        tags["album"] = parts[1]
    elif len(parts) == 1:
        segment = parts[0]
        # Try "(YEAR) Artist - Album [FORMAT]"
        m = re.match(r"\((\d{4})\)\s+(.+?)\s*-\s*(.+?)(?:\s*\[.+\])?\s*$", segment)
        if m:
            tags["date"] = m.group(1)
            tags["artist"] = m.group(2).strip()
            tags["album"] = m.group(3).strip()
        else:
            # Try "Artist - Album (YEAR) FORMAT"
            m2 = re.match(r"(.+?)\s*-\s*(.+?)(?:\s*\(\d{4}\))?(?:\s+\w+)?\s*$", segment)
            if m2:
                tags["artist"] = m2.group(1).strip()
                tags["album"] = m2.group(2).strip()

    # Extract year from directory name if not already found
    if "date" not in tags:
        year_match = re.search(r"\((\d{4})\)", dir_part)
        if year_match:
            tags["date"] = year_match.group(1)

    return tags


def _sidecar_path(full_path: Path) -> Path:
    """Return the hash-based sidecar path for a file.

    Uses sha256(str(path))[:16] naming to handle long filenames safely,
    matching the scheme in resonance.core.identity.signature._read_stub_metadata.
    """
    path_hash = hashlib.sha256(str(full_path).encode("utf-8")).hexdigest()[:16]
    return full_path.parent / f"{path_hash}.meta.json"


def build_library_from_metadata(
    metadata: dict[str, Any],
    library_root: Path,
) -> None:
    """Create stub files and `.meta.json` sidecars under *library_root*.

    For every audio file listed in *metadata['files']*:
    1. Touch a 0-byte stub at ``library_root / entry['path']``.
    2. Write a ``.meta.json`` sidecar (both hash-based and suffix-based
       naming) containing ``duration_seconds`` and ``tags`` parsed from
       the path and any available ``audio_info``.

    Non-audio files get a stub only (no sidecar).
    """
    for file_info in metadata["files"]:
        rel_path: str = file_info["path"]
        full_path = library_root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if not full_path.exists():
            full_path.touch()

        if not file_info.get("is_audio", False):
            continue

        # Build sidecar content
        duration: int | None = None
        audio_info = file_info.get("audio_info")
        if isinstance(audio_info, dict):
            raw = audio_info.get("duration")
            if isinstance(raw, (int, float)):
                duration = int(raw)

        tags = _parse_tags_from_path(rel_path)
        if duration is not None:
            tags["duration"] = str(duration)

        sidecar: dict[str, Any] = {}
        if duration is not None:
            sidecar["duration_seconds"] = duration
        if tags:
            sidecar["tags"] = tags

        if not sidecar:
            continue

        # Write hash-based sidecar (for signature.py)
        hash_path = _sidecar_path(full_path)
        hash_path.write_text(json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")

        # Write suffix-based sidecar (for identifier.py / scan.py)
        # Skip if the resulting filename would exceed filesystem limits.
        suffix_path = full_path.with_suffix(full_path.suffix + ".meta.json")
        if len(suffix_path.name.encode("utf-8")) <= 255:
            suffix_path.write_text(json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")
