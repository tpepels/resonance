"""Audit remediation tests for deterministic timestamps."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from resonance.infrastructure.cache import MetadataCache
from resonance.infrastructure.directory_store import DirectoryStateStore


def test_metadata_cache_timestamps_are_utc_z(tmp_path: Path) -> None:
    fixed = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    cache = MetadataCache(tmp_path / "cache.db", now_fn=lambda: fixed)
    try:
        cache.set("k1", {"a": 1}, namespace="musicbrainz:release")
        cache.set("k2", {"b": 2}, namespace="musicbrainz:release")
    finally:
        cache.close()

    conn = sqlite3.connect(tmp_path / "cache.db")
    try:
        rows = conn.execute(
            "SELECT updated_at FROM cache WHERE namespace = ? ORDER BY key ASC",
            ("musicbrainz:release",),
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("2020-01-01T12:00:00Z",), ("2020-01-01T12:00:00Z",)]


def test_directory_store_timestamps_are_utc_z(tmp_path: Path) -> None:
    fixed = datetime(2021, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
    store = DirectoryStateStore(tmp_path / "state.db", now_fn=lambda: fixed)
    try:
        record = store.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert record.created_at == "2021-02-03T04:05:06Z"
        assert record.updated_at == "2021-02-03T04:05:06Z"
    finally:
        store.close()
