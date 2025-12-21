"""Tests for cache schema versioning behavior."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from resonance.infrastructure.cache import MetadataCache


def test_cache_schema_missing_metadata_purges(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.db"
    conn = sqlite3.connect(cache_path)
    try:
        conn.execute(
            """
            CREATE TABLE cache (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(namespace, key)
            )
            """
        )
        conn.execute(
            "INSERT INTO cache (namespace, key, value, updated_at) VALUES (?, ?, ?, ?)",
            ("musicbrainz:release", "mb-1", json.dumps({"id": "mb-1"}), "now"),
        )
        conn.commit()
    finally:
        conn.close()

    cache = MetadataCache(cache_path)
    cache.close()

    conn = sqlite3.connect(cache_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        version = conn.execute(
            "SELECT value FROM schema_metadata WHERE key = ?",
            ("schema_version",),
        ).fetchone()[0]
    finally:
        conn.close()

    assert count == 0
    assert version == "1"
