"""Integration tests for prescan CLI."""

from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path
import sqlite3

from resonance.commands.prescan import run_prescan
from resonance.core.identity.matching import normalize_token
from resonance.infrastructure.cache import MetadataCache


def _write_stub_audio(path: Path, **tags: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub")
    metadata = {
        "title": tags.get("title"),
        "artist": tags.get("artist"),
        "album_artist": tags.get("album_artist"),
        "composer": tags.get("composer"),
        "performer": tags.get("performer"),
        "conductor": tags.get("conductor"),
    }
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(metadata))
    return path


def test_prescan_records_canonical_mappings(tmp_path: Path) -> None:
    library = tmp_path / "library"
    _write_stub_audio(
        library / "album" / "01 - Track A.flac",
        artist=" Artist A ",
        album_artist="Album Artist A",
        composer="Composer A",
        performer="Performer A",
        conductor="Conductor A",
    )
    _write_stub_audio(
        library / "album" / "02 - Track B.flac",
        artist="Artist B",
        album_artist="Album Artist B",
    )

    cache_path = tmp_path / "cache.db"
    args = Namespace(directory=library, cache=cache_path)
    run_prescan(args)

    cache = MetadataCache(cache_path)
    try:
        mappings = {
            ("artist", "Artist A"),
            ("album_artist", "Album Artist A"),
            ("composer", "Composer A"),
            ("performer", "Performer A"),
            ("conductor", "Conductor A"),
            ("artist", "Artist B"),
            ("album_artist", "Album Artist B"),
        }
        for category, value in mappings:
            key = f"{category}::{normalize_token(value)}"
            assert cache.get_canonical_name(key) == value.strip()
    finally:
        cache.close()


def test_prescan_does_not_pin_release(tmp_path: Path) -> None:
    library = tmp_path / "library"
    _write_stub_audio(
        library / "album" / "01 - Track A.flac",
        artist="Artist A",
    )

    cache_path = tmp_path / "cache.db"
    args = Namespace(directory=library, cache=cache_path)
    run_prescan(args)

    conn = sqlite3.connect(cache_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM directory_releases").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_prescan_skips_non_audio_only_dirs(tmp_path: Path) -> None:
    library = tmp_path / "library"
    non_audio_dir = library / "docs"
    non_audio_dir.mkdir(parents=True, exist_ok=True)
    (non_audio_dir / "readme.txt").write_text("notes")

    cache_path = tmp_path / "cache.db"
    args = Namespace(directory=library, cache=cache_path)
    run_prescan(args)

    conn = sqlite3.connect(cache_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM canonical_names").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_prescan_conflict_resolution_is_deterministic(tmp_path: Path) -> None:
    library = tmp_path / "library"
    _write_stub_audio(
        library / "a" / "01 - Track A.flac",
        artist="Artist A",
    )
    _write_stub_audio(
        library / "b" / "01 - Track B.flac",
        artist="artist a",
    )

    cache_path = tmp_path / "cache.db"
    args = Namespace(directory=library, cache=cache_path)
    run_prescan(args)

    cache = MetadataCache(cache_path)
    try:
        key = f"artist::{normalize_token('Artist A')}"
        assert cache.get_canonical_name(key) == "Artist A"
    finally:
        cache.close()
