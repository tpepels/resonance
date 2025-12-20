"""SQLite-backed cache for Resonance.

Provides persistent storage for:
- Provider API responses (MusicBrainz, Discogs)
- Directory release decisions
- Canonical name mappings
- Deferred prompts
- File move tracking
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Optional


class MetadataCache:
    """SQLite-backed cache for expensive operations and user decisions."""

    def __init__(self, path: Path, cache_limit_per_namespace: int | None = None) -> None:
        """Initialize the cache.

        Args:
            path: Path to SQLite database file
            cache_limit_per_namespace: Optional deterministic limit per namespace
        """
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._cache_limit_per_namespace = cache_limit_per_namespace
        self._init_schema()

    def _init_schema(self) -> None:
        """Create database schema."""
        # Generic key-value cache for API responses
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(namespace, key)
            )
            """
        )

        # Track processed files (for idempotency)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_files (
                path TEXT PRIMARY KEY,
                mtime_ns INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                fingerprint TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Remember user's release choices per directory
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS directory_releases (
                directory_path TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                release_id TEXT NOT NULL,
                match_confidence REAL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Canonical name mappings
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS canonical_names (
                cache_key TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Deferred prompts (for daemon mode)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deferred_prompts (
                directory_path TEXT PRIMARY KEY,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Skipped/jailed directories
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skipped_directories (
                directory_path TEXT PRIMARY KEY,
                reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # File move tracking (for transaction support)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS file_moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                target_path TEXT NOT NULL,
                moved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()

    # Generic cache operations
    def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key
            namespace: Cache namespace (e.g., "musicbrainz", "discogs")

        Returns:
            Cached value (deserialized from JSON) or None
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM cache WHERE namespace = ? AND key = ?",
                (namespace, key),
            ).fetchone()

            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return None
            return None

    def set(self, key: str, value: Any, namespace: str = "default") -> None:
        """Store value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            namespace: Cache namespace
        """
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (namespace, key, value, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (namespace, key, json.dumps(value), datetime.now().isoformat()),
            )
            self._enforce_cache_limit(namespace)
            self._conn.commit()

    def _enforce_cache_limit(self, namespace: str) -> None:
        """Evict cache entries deterministically when limits are set."""
        if self._cache_limit_per_namespace is None:
            return
        rows = self._conn.execute(
            "SELECT key FROM cache WHERE namespace = ? ORDER BY key ASC",
            (namespace,),
        ).fetchall()
        if len(rows) <= self._cache_limit_per_namespace:
            return
        excess = rows[self._cache_limit_per_namespace :]
        keys = [row[0] for row in excess]
        self._conn.executemany(
            "DELETE FROM cache WHERE namespace = ? AND key = ?",
            [(namespace, key) for key in keys],
        )

    # MusicBrainz cache
    def get_mb_release(self, release_id: str) -> Optional[dict[str, Any]]:
        """Get cached MusicBrainz release."""
        return self.get(release_id, namespace="musicbrainz:release")

    def set_mb_release(self, release_id: str, data: dict[str, Any]) -> None:
        """Cache MusicBrainz release."""
        self.set(release_id, data, namespace="musicbrainz:release")

    def get_mb_recording(self, recording_id: str) -> Optional[dict[str, Any]]:
        """Get cached MusicBrainz recording."""
        return self.get(recording_id, namespace="musicbrainz:recording")

    def set_mb_recording(self, recording_id: str, data: dict[str, Any]) -> None:
        """Cache MusicBrainz recording."""
        self.set(recording_id, data, namespace="musicbrainz:recording")

    # Discogs cache
    def get_discogs_release(self, release_id: str) -> Optional[dict[str, Any]]:
        """Get cached Discogs release."""
        return self.get(release_id, namespace="discogs:release")

    def set_discogs_release(self, release_id: str, data: dict[str, Any]) -> None:
        """Cache Discogs release."""
        self.set(release_id, data, namespace="discogs:release")

    # Directory release decisions
    def get_directory_release(self, directory: Path) -> Optional[tuple[str, str, float]]:
        """Get remembered release for a directory.

        Returns:
            Tuple of (provider, release_id, confidence) or None
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT provider, release_id, match_confidence "
                "FROM directory_releases WHERE directory_path = ?",
                (str(directory),),
            ).fetchone()

            if row:
                return (row[0], row[1], row[2] if row[2] is not None else 0.0)
            return None

    def set_directory_release(
        self, directory: Path, provider: str, release_id: str, confidence: float = 0.0
    ) -> None:
        """Remember release choice for a directory."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO directory_releases "
                "(directory_path, provider, release_id, match_confidence, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (str(directory), provider, release_id, confidence, datetime.now().isoformat()),
            )
            self._conn.commit()

    # Canonical names (for identity system)
    def get_canonical_name(self, cache_key: str) -> Optional[str]:
        """Get canonical name for a cache key.

        Args:
            cache_key: Key like "artist::beethoven" or "composer::bach"

        Returns:
            Canonical name or None
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT canonical_name FROM canonical_names WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()

            return row[0] if row else None

    def set_canonical_name(self, cache_key: str, canonical_name: str) -> None:
        """Store canonical name mapping."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO canonical_names (cache_key, canonical_name, updated_at) "
                "VALUES (?, ?, ?)",
                (cache_key, canonical_name, datetime.now().isoformat()),
            )
            self._conn.commit()

    # Deferred prompts
    def add_deferred_prompt(self, directory: Path, reason: str) -> None:
        """Mark directory as needing user prompt."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO deferred_prompts (directory_path, reason, created_at) "
                "VALUES (?, ?, ?)",
                (str(directory), reason, datetime.now().isoformat()),
            )
            self._conn.commit()

    def get_deferred_prompts(self) -> list[tuple[Path, str]]:
        """Get all directories needing prompts.

        Returns:
            List of (directory, reason) tuples
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT directory_path, reason FROM deferred_prompts ORDER BY created_at"
            ).fetchall()

            return [(Path(row[0]), row[1]) for row in rows]

    def remove_deferred_prompt(self, directory: Path) -> None:
        """Remove directory from deferred prompts."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM deferred_prompts WHERE directory_path = ?", (str(directory),)
            )
            self._conn.commit()

    # Skipped directories
    def add_skipped_directory(self, directory: Path, reason: str = "user_skipped") -> None:
        """Mark directory as skipped (jailed)."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO skipped_directories (directory_path, reason, created_at) "
                "VALUES (?, ?, ?)",
                (str(directory), reason, datetime.now().isoformat()),
            )
            self._conn.commit()

    def is_directory_skipped(self, directory: Path) -> bool:
        """Check if directory is skipped."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM skipped_directories WHERE directory_path = ?", (str(directory),)
            ).fetchone()

            return row is not None

    def unjail_directories(self) -> int:
        """Remove all skipped directories (--unjail).

        Returns:
            Number of directories unjailed
        """
        with self._lock:
            cursor = self._conn.execute("DELETE FROM skipped_directories")
            self._conn.commit()
            return cursor.rowcount

    # File move tracking
    def record_move(self, source: Path, target: Path) -> None:
        """Record a file move (for transaction support)."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO file_moves (source_path, target_path, moved_at) VALUES (?, ?, ?)",
                (str(source), str(target), datetime.now().isoformat()),
            )
            self._conn.commit()
