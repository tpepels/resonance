"""Directory state persistence keyed by dir_id."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from resonance.core.state import DirectoryRecord, DirectoryState
from resonance import __version__ as RESONANCE_VERSION


class DirectoryStateStore:
    """SQLite-backed store for directory state records."""

    def __init__(self, path: Path, now_fn=None, app_version: Optional[str] = None) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._logger = logging.getLogger(__name__)
        self._app_version = app_version or RESONANCE_VERSION
        try:
            self._init_schema()
            self._ensure_active_version()
        except Exception:
            self._conn.close()
            raise

    def _now_iso(self) -> str:
        value = self._now_fn()
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS directories (
                dir_id TEXT PRIMARY KEY CHECK(length(dir_id) > 0 AND length(dir_id) <= 64),
                last_seen_path TEXT NOT NULL,
                signature_hash TEXT NOT NULL CHECK(length(signature_hash) = 64 AND signature_hash GLOB '[0-9a-f]*'),
                signature_version INTEGER NOT NULL DEFAULT 1 CHECK(signature_version >= 1),
                state TEXT NOT NULL,
                pinned_provider TEXT,
                pinned_release_id TEXT,
                pinned_confidence REAL CHECK(pinned_confidence IS NULL OR (pinned_confidence >= 0 AND pinned_confidence <= 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._ensure_audit_artifacts_table()
        self._ensure_signature_version_column()
        self._ensure_schema_version()
        self._conn.commit()

    def _ensure_signature_version_column(self) -> None:
        columns = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(directories)").fetchall()
        }
        if "signature_version" in columns:
            return
        self._conn.execute(
            "ALTER TABLE directories ADD COLUMN signature_version INTEGER DEFAULT 1"
        )

    def _ensure_schema_version(self) -> None:
        current_version = 4
        version = self._get_metadata("schema_version")
        if version is None:
            row = self._conn.execute("SELECT COUNT(*) FROM directories").fetchone()
            if row and row[0] > 0:
                raise ValueError(
                    "State DB missing schema_version - created by old version?"
                )
            self._set_metadata("schema_version", str(current_version))
            self._set_metadata("created_by_version", "0.1.0")
            return
        if int(version) > current_version:
            raise ValueError(
                f"DB schema {version} > supported {current_version}. "
                "Please upgrade Resonance."
            )
        if int(version) < current_version:
            self._migrate_schema(int(version), current_version)

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _ensure_active_version(self) -> None:
        active_version = self._get_metadata("active_app_version")
        active_pid = self._get_metadata("active_app_pid")
        if active_version and active_pid:
            try:
                pid = int(active_pid)
            except ValueError:
                pid = 0
            if self._pid_alive(pid) and active_version != self._app_version:
                raise ValueError(
                    "State DB already in use by app version "
                    f"{active_version} (pid {pid}). Refusing to open with {self._app_version}."
                )
        self._set_metadata("active_app_version", self._app_version)
        self._set_metadata("active_app_pid", str(os.getpid()))
        self._conn.commit()

    def _migrate_schema(self, from_version: int, current_version: int) -> None:
        for version in range(from_version, current_version):
            if version == 1:
                self._ensure_signature_version_column()
            if version == 2:
                self._rebuild_directories_with_constraints()
            if version == 3:
                self._ensure_audit_artifacts_table()
            self._set_metadata("schema_version", str(version + 1))

    def _rebuild_directories_with_constraints(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE directories_new (
                dir_id TEXT PRIMARY KEY CHECK(length(dir_id) > 0 AND length(dir_id) <= 64),
                last_seen_path TEXT NOT NULL,
                signature_hash TEXT NOT NULL CHECK(length(signature_hash) = 64 AND signature_hash GLOB '[0-9a-f]*'),
                signature_version INTEGER NOT NULL DEFAULT 1 CHECK(signature_version >= 1),
                state TEXT NOT NULL,
                pinned_provider TEXT,
                pinned_release_id TEXT,
                pinned_confidence REAL CHECK(pinned_confidence IS NULL OR (pinned_confidence >= 0 AND pinned_confidence <= 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            INSERT INTO directories_new (
                dir_id, last_seen_path, signature_hash, signature_version, state,
                pinned_provider, pinned_release_id, pinned_confidence,
                created_at, updated_at
            )
            SELECT dir_id, last_seen_path, signature_hash, signature_version, state,
                   pinned_provider, pinned_release_id, pinned_confidence,
                   created_at, updated_at
            FROM directories
            """
        )
        self._conn.execute("DROP TABLE directories")
        self._conn.execute("ALTER TABLE directories_new RENAME TO directories")

    def _ensure_audit_artifacts_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_artifacts (
                dir_id TEXT PRIMARY KEY,
                last_plan_hash TEXT,
                last_plan_version TEXT,
                last_apply_status TEXT,
                last_apply_errors TEXT,
                last_apply_updated_at TEXT
            )
            """
        )

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

    def record_plan_summary(self, dir_id: str, plan_hash: str, plan_version: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO audit_artifacts (
                    dir_id, last_plan_hash, last_plan_version, last_apply_status,
                    last_apply_errors, last_apply_updated_at
                )
                VALUES (
                    ?, ?, ?,
                    COALESCE((SELECT last_apply_status FROM audit_artifacts WHERE dir_id = ?), NULL),
                    COALESCE((SELECT last_apply_errors FROM audit_artifacts WHERE dir_id = ?), NULL),
                    COALESCE((SELECT last_apply_updated_at FROM audit_artifacts WHERE dir_id = ?), NULL)
                )
                """,
                (dir_id, plan_hash, plan_version, dir_id, dir_id, dir_id),
            )
            self._conn.commit()

    def record_apply_summary(
        self, dir_id: str, status: str, errors: tuple[str, ...]
    ) -> None:
        now = self._now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO audit_artifacts (
                    dir_id, last_plan_hash, last_plan_version,
                    last_apply_status, last_apply_errors, last_apply_updated_at
                )
                VALUES (
                    ?,
                    COALESCE((SELECT last_plan_hash FROM audit_artifacts WHERE dir_id = ?), NULL),
                    COALESCE((SELECT last_plan_version FROM audit_artifacts WHERE dir_id = ?), NULL),
                    ?, ?, ?
                )
                """,
                (dir_id, dir_id, dir_id, status, json.dumps(list(errors)), now),
            )
            self._conn.commit()

    def get_audit_artifacts(self, dir_id: str) -> dict[str, str | None | tuple[str, ...]]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT last_plan_hash, last_plan_version,
                       last_apply_status, last_apply_errors, last_apply_updated_at
                FROM audit_artifacts
                WHERE dir_id = ?
                """,
                (dir_id,),
            ).fetchone()
        if not row:
            return {}
        errors = tuple(json.loads(row[3])) if row[3] else ()
        return {
            "last_plan_hash": row[0],
            "last_plan_version": row[1],
            "last_apply_status": row[2],
            "last_apply_errors": errors,
            "last_apply_updated_at": row[4],
        }

    def close(self) -> None:
        with self._lock:
            try:
                self._set_metadata("active_app_version", "")
                self._set_metadata("active_app_pid", "")
                self._conn.commit()
            except sqlite3.Error:
                pass
            self._conn.close()

    def list_by_state(self, state: DirectoryState) -> list[DirectoryRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT dir_id, last_seen_path, signature_hash, signature_version, state,
                       pinned_provider, pinned_release_id, pinned_confidence,
                       created_at, updated_at
                FROM directories
                WHERE state = ?
                ORDER BY dir_id ASC
                """,
                (state.value,),
            ).fetchall()

        return [
            DirectoryRecord(
                dir_id=row[0],
                last_seen_path=Path(row[1]),
                signature_hash=row[2],
                signature_version=row[3],
                state=DirectoryState(row[4]),
                pinned_provider=row[5],
                pinned_release_id=row[6],
                pinned_confidence=row[7],
                created_at=row[8],
                updated_at=row[9],
            )
            for row in rows
        ]

    def list_all(self) -> list[DirectoryRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT dir_id, last_seen_path, signature_hash, signature_version, state,
                       pinned_provider, pinned_release_id, pinned_confidence,
                       created_at, updated_at
                FROM directories
                ORDER BY dir_id ASC
                """
            ).fetchall()

        return [
            DirectoryRecord(
                dir_id=row[0],
                last_seen_path=Path(row[1]),
                signature_hash=row[2],
                signature_version=row[3],
                state=DirectoryState(row[4]),
                pinned_provider=row[5],
                pinned_release_id=row[6],
                pinned_confidence=row[7],
                created_at=row[8],
                updated_at=row[9],
            )
            for row in rows
        ]

    def get(self, dir_id: str) -> Optional[DirectoryRecord]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT dir_id, last_seen_path, signature_hash, signature_version, state,
                       pinned_provider, pinned_release_id, pinned_confidence,
                       created_at, updated_at
                FROM directories
                WHERE dir_id = ?
                """,
                (dir_id,),
            ).fetchone()

        if not row:
            return None

        return DirectoryRecord(
            dir_id=row[0],
            last_seen_path=Path(row[1]),
            signature_hash=row[2],
            signature_version=row[3],
            state=DirectoryState(row[4]),
            pinned_provider=row[5],
            pinned_release_id=row[6],
            pinned_confidence=row[7],
            created_at=row[8],
            updated_at=row[9],
        )

    def upsert(self, record: DirectoryRecord) -> DirectoryRecord:
        now = self._now_iso()
        created_at = record.created_at or now
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO directories (
                    dir_id, last_seen_path, signature_hash, signature_version, state,
                    pinned_provider, pinned_release_id, pinned_confidence,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.dir_id,
                    str(record.last_seen_path),
                    record.signature_hash,
                    record.signature_version,
                    record.state.value,
                    record.pinned_provider,
                    record.pinned_release_id,
                    record.pinned_confidence,
                    created_at,
                    now,
                ),
            )
            self._conn.commit()

        return DirectoryRecord(
            dir_id=record.dir_id,
            last_seen_path=record.last_seen_path,
            signature_hash=record.signature_hash,
            signature_version=record.signature_version,
            state=record.state,
            pinned_provider=record.pinned_provider,
            pinned_release_id=record.pinned_release_id,
            pinned_confidence=record.pinned_confidence,
            created_at=created_at,
            updated_at=now,
        )

    def get_or_create(
        self,
        dir_id: str,
        path: Path,
        signature_hash: str,
        signature_version: int = 1,
    ) -> DirectoryRecord:
        existing = self.get(dir_id)
        if not existing:
            record = DirectoryRecord(
                dir_id=dir_id,
                last_seen_path=path,
                signature_hash=signature_hash,
                signature_version=signature_version,
                state=DirectoryState.NEW,
            )
            return self.upsert(record)

        updated = existing
        if (
            existing.signature_hash != signature_hash
            or existing.signature_version != signature_version
        ):
            if existing.signature_version != signature_version:
                self._logger.warning(
                    "Signature algorithm changed (v%s -> v%s). Resetting state.",
                    existing.signature_version,
                    signature_version,
                )
            updated = DirectoryRecord(
                dir_id=existing.dir_id,
                last_seen_path=path,
                signature_hash=signature_hash,
                signature_version=signature_version,
                state=DirectoryState.NEW,
                pinned_provider=None,
                pinned_release_id=None,
                pinned_confidence=None,
                created_at=existing.created_at,
            )
        elif existing.last_seen_path != path:
            updated = DirectoryRecord(
                dir_id=existing.dir_id,
                last_seen_path=path,
                signature_hash=existing.signature_hash,
                signature_version=existing.signature_version,
                state=existing.state,
                pinned_provider=existing.pinned_provider,
                pinned_release_id=existing.pinned_release_id,
                pinned_confidence=existing.pinned_confidence,
                created_at=existing.created_at,
            )

        if updated is existing:
            return existing

        return self.upsert(updated)

    def set_state(
        self,
        dir_id: str,
        state: DirectoryState,
        pinned_provider: Optional[str] = None,
        pinned_release_id: Optional[str] = None,
        pinned_confidence: Optional[float] = None,
    ) -> DirectoryRecord:
        record = self.get(dir_id)
        if not record:
            raise KeyError(f"Unknown dir_id: {dir_id}")

        # RESOLVED states require both provider and release_id
        if state in (DirectoryState.RESOLVED_AUTO, DirectoryState.RESOLVED_USER):
            if not pinned_provider or not pinned_release_id:
                raise ValueError(
                    f"State {state.value} requires both pinned_provider and pinned_release_id"
                )

        updated = DirectoryRecord(
            dir_id=record.dir_id,
            last_seen_path=record.last_seen_path,
            signature_hash=record.signature_hash,
            signature_version=record.signature_version,
            state=state,
            pinned_provider=pinned_provider if pinned_release_id else None,
            pinned_release_id=pinned_release_id,
            pinned_confidence=pinned_confidence if pinned_release_id else None,
            created_at=record.created_at,
        )
        return self.upsert(updated)

    def unjail(self, dir_id: str) -> DirectoryRecord:
        record = self.get(dir_id)
        if not record:
            raise KeyError(f"Unknown dir_id: {dir_id}")

        updated = DirectoryRecord(
            dir_id=record.dir_id,
            last_seen_path=record.last_seen_path,
            signature_hash=record.signature_hash,
            signature_version=record.signature_version,
            state=DirectoryState.NEW,
            pinned_provider=None,
            pinned_release_id=None,
            pinned_confidence=None,
            created_at=record.created_at,
        )
        return self.upsert(updated)
