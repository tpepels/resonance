"""Tests for deterministic cache bounding."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from resonance.infrastructure.cache import MetadataCache


def test_cache_evicts_deterministically_by_key(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.db"
    cache = MetadataCache(cache_path, cache_limit_per_namespace=2)
    try:
        cache.set("b", {"value": 1}, namespace="musicbrainz:release")
        cache.set("a", {"value": 2}, namespace="musicbrainz:release")
        cache.set("c", {"value": 3}, namespace="musicbrainz:release")
    finally:
        cache.close()

    conn = sqlite3.connect(cache_path)
    try:
        rows = conn.execute(
            "SELECT key FROM cache WHERE namespace = ? ORDER BY key ASC",
            ("musicbrainz:release",),
        ).fetchall()
    finally:
        conn.close()

    keys = [row[0] for row in rows]
    assert keys == ["a", "b"]


def test_cache_eviction_is_deterministic_across_reopen(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.db"
    cache = MetadataCache(cache_path, cache_limit_per_namespace=2)
    try:
        cache.set("b", {"value": 1}, namespace="musicbrainz:release")
        cache.set("a", {"value": 2}, namespace="musicbrainz:release")
    finally:
        cache.close()

    cache = MetadataCache(cache_path, cache_limit_per_namespace=2)
    try:
        cache.set("c", {"value": 3}, namespace="musicbrainz:release")
    finally:
        cache.close()

    conn = sqlite3.connect(cache_path)
    try:
        rows = conn.execute(
            "SELECT key FROM cache WHERE namespace = ? ORDER BY key ASC",
            ("musicbrainz:release",),
        ).fetchall()
    finally:
        conn.close()

    keys = [row[0] for row in rows]
    assert keys == ["a", "b"]
