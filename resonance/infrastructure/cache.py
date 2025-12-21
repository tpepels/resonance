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
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from .provider_cache import canonical_json, provider_cache_key


class MetadataCache:
    """SQLite-backed cache for expensive operations and user decisions."""

    def __init__(
        self,
        path: Path,
        cache_limit_per_namespace: int | None = None,
        now_fn=None,
    ) -> None:
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
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._init_schema()

    def _now_iso(self) -> str:
        value = self._now_fn()
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _init_schema(self) -> None:
        """Create database schema."""
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        schema_version = self._get_metadata("schema_version")
        if schema_version is None or schema_version != "1":
            self._purge_schema()
            self._set_metadata("schema_version", "1")
            self._set_metadata("created_by_version", "0.1.0")

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
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS directory_releases_by_id (
                dir_id TEXT PRIMARY KEY,
                directory_path TEXT,
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
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deferred_prompts_by_id (
                dir_id TEXT PRIMARY KEY,
                directory_path TEXT,
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
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skipped_directories_by_id (
                dir_id TEXT PRIMARY KEY,
                directory_path TEXT,
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

    def _purge_schema(self) -> None:
        tables = (
            "cache",
            "processed_files",
            "directory_releases",
            "directory_releases_by_id",
            "canonical_names",
            "deferred_prompts",
            "deferred_prompts_by_id",
            "skipped_directories",
            "skipped_directories_by_id",
            "file_moves",
        )
        for table in tables:
            self._conn.execute(f"DROP TABLE IF EXISTS {table}")

    def _get_metadata(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM schema_metadata WHERE key = ?",
            (key,),
        ).fetchone()
        return row[0] if row else None

    def _set_metadata(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_metadata (key, value) VALUES (?, ?)",
            (key, value),
        )

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
            payload = canonical_json(value)
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (namespace, key, value, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (namespace, key, payload, self._now_iso()),
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
    def get_mb_release(
        self,
        release_id: str,
        *,
        cache_version: str = "v1",
        client_version: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get cached MusicBrainz release."""
        if client_version:
            key = provider_cache_key(
                provider="musicbrainz",
                request_type="release",
                query={"id": release_id},
                version=cache_version,
                client_version=client_version,
            )
            cached = self.get(key, namespace="musicbrainz:release")
            if cached is not None:
                return cached
        return self.get(release_id, namespace="musicbrainz:release")

    def set_mb_release(
        self,
        release_id: str,
        data: dict[str, Any],
        *,
        cache_version: str = "v1",
        client_version: Optional[str] = None,
    ) -> None:
        """Cache MusicBrainz release."""
        if client_version:
            key = provider_cache_key(
                provider="musicbrainz",
                request_type="release",
                query={"id": release_id},
                version=cache_version,
                client_version=client_version,
            )
        else:
            key = release_id
        self.set(key, data, namespace="musicbrainz:release")

    def get_mb_recording(
        self,
        recording_id: str,
        *,
        cache_version: str = "v1",
        client_version: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get cached MusicBrainz recording."""
        if client_version:
            key = provider_cache_key(
                provider="musicbrainz",
                request_type="recording",
                query={"id": recording_id},
                version=cache_version,
                client_version=client_version,
            )
            cached = self.get(key, namespace="musicbrainz:recording")
            if cached is not None:
                return cached
        return self.get(recording_id, namespace="musicbrainz:recording")

    def set_mb_recording(
        self,
        recording_id: str,
        data: dict[str, Any],
        *,
        cache_version: str = "v1",
        client_version: Optional[str] = None,
    ) -> None:
        """Cache MusicBrainz recording."""
        if client_version:
            key = provider_cache_key(
                provider="musicbrainz",
                request_type="recording",
                query={"id": recording_id},
                version=cache_version,
                client_version=client_version,
            )
        else:
            key = recording_id
        self.set(key, data, namespace="musicbrainz:recording")

    # Discogs cache
    def get_discogs_release(
        self,
        release_id: str,
        *,
        cache_version: str = "v1",
        client_version: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Get cached Discogs release."""
        if client_version:
            key = provider_cache_key(
                provider="discogs",
                request_type="release",
                query={"id": release_id},
                version=cache_version,
                client_version=client_version,
            )
            cached = self.get(key, namespace="discogs:release")
            if cached is not None:
                return cached
        return self.get(release_id, namespace="discogs:release")

    def set_discogs_release(
        self,
        release_id: str,
        data: dict[str, Any],
        *,
        cache_version: str = "v1",
        client_version: Optional[str] = None,
    ) -> None:
        """Cache Discogs release."""
        if client_version:
            key = provider_cache_key(
                provider="discogs",
                request_type="release",
                query={"id": release_id},
                version=cache_version,
                client_version=client_version,
            )
        else:
            key = release_id
        self.set(key, data, namespace="discogs:release")

    # Directory release decisions
    def get_directory_release_by_id(
        self, dir_id: str
    ) -> Optional[tuple[str, str, float]]:
        """Get remembered release for a directory id."""
        with self._lock:
            row = self._conn.execute(
                "SELECT provider, release_id, match_confidence "
                "FROM directory_releases_by_id WHERE dir_id = ?",
                (dir_id,),
            ).fetchone()
            if row:
                return (row[0], row[1], row[2] if row[2] is not None else 0.0)
            return None

    def set_directory_release_by_id(
        self,
        dir_id: str,
        directory_path: Optional[Path],
        provider: str,
        release_id: str,
        confidence: float = 0.0,
    ) -> None:
        """Remember release choice keyed by directory id."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO directory_releases_by_id "
                "(dir_id, directory_path, provider, release_id, match_confidence, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    dir_id,
                    str(directory_path) if directory_path is not None else None,
                    provider,
                    release_id,
                    confidence,
                    self._now_iso(),
                ),
            )
            self._conn.commit()

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
                (str(directory), provider, release_id, confidence, self._now_iso()),
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
                (cache_key, canonical_name, self._now_iso()),
            )
            self._conn.commit()

    # Deferred prompts
    def add_deferred_prompt_by_id(
        self, dir_id: str, directory_path: Optional[Path], reason: str
    ) -> None:
        """Mark directory as needing user prompt keyed by directory id."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO deferred_prompts_by_id "
                "(dir_id, directory_path, reason, created_at) VALUES (?, ?, ?, ?)",
                (
                    dir_id,
                    str(directory_path) if directory_path is not None else None,
                    reason,
                    self._now_iso(),
                ),
            )
            self._conn.commit()

    def get_deferred_prompts_by_id(self) -> list[tuple[str, Optional[Path], str]]:
        """Get all directories needing prompts keyed by id."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT dir_id, directory_path, reason FROM deferred_prompts_by_id "
                "ORDER BY created_at"
            ).fetchall()
            if rows:
                return [
                    (row[0], Path(row[1]) if row[1] else None, row[2]) for row in rows
                ]
            legacy_rows = self._conn.execute(
                "SELECT directory_path, reason FROM deferred_prompts ORDER BY created_at"
            ).fetchall()
            return [
                ("", Path(row[0]), row[1]) for row in legacy_rows
            ]

    def remove_deferred_prompt_by_id(self, dir_id: str) -> None:
        """Remove directory from deferred prompts keyed by id."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM deferred_prompts_by_id WHERE dir_id = ?", (dir_id,)
            )
            self._conn.commit()

    def add_deferred_prompt(self, directory: Path, reason: str) -> None:
        """Mark directory as needing user prompt."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO deferred_prompts (directory_path, reason, created_at) "
                "VALUES (?, ?, ?)",
                (str(directory), reason, self._now_iso()),
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
    def add_skipped_directory_by_id(
        self, dir_id: str, directory_path: Optional[Path], reason: str = "user_skipped"
    ) -> None:
        """Mark directory as skipped (jailed) keyed by directory id."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO skipped_directories_by_id "
                "(dir_id, directory_path, reason, created_at) VALUES (?, ?, ?, ?)",
                (
                    dir_id,
                    str(directory_path) if directory_path is not None else None,
                    reason,
                    self._now_iso(),
                ),
            )
            self._conn.commit()

    def is_directory_skipped_by_id(self, dir_id: str) -> bool:
        """Check if directory id is skipped."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM skipped_directories_by_id WHERE dir_id = ?",
                (dir_id,),
            ).fetchone()
            return row is not None

    def add_skipped_directory(self, directory: Path, reason: str = "user_skipped") -> None:
        """Mark directory as skipped (jailed)."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO skipped_directories (directory_path, reason, created_at) "
                "VALUES (?, ?, ?)",
                (str(directory), reason, self._now_iso()),
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
                (str(source), str(target), self._now_iso()),
            )
            self._conn.commit()
