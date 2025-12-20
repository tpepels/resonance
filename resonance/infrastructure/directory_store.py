"""Directory state persistence keyed by dir_id."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

from resonance.core.state import DirectoryRecord, DirectoryState


class DirectoryStateStore:
    """SQLite-backed store for directory state records."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS directories (
                dir_id TEXT PRIMARY KEY,
                last_seen_path TEXT NOT NULL,
                signature_hash TEXT NOT NULL,
                state TEXT NOT NULL,
                pinned_provider TEXT,
                pinned_release_id TEXT,
                pinned_confidence REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def list_by_state(self, state: DirectoryState) -> list[DirectoryRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT dir_id, last_seen_path, signature_hash, state,
                       pinned_provider, pinned_release_id, pinned_confidence,
                       created_at, updated_at
                FROM directories
                WHERE state = ?
                """,
                (state.value,),
            ).fetchall()

        return [
            DirectoryRecord(
                dir_id=row[0],
                last_seen_path=Path(row[1]),
                signature_hash=row[2],
                state=DirectoryState(row[3]),
                pinned_provider=row[4],
                pinned_release_id=row[5],
                pinned_confidence=row[6],
                created_at=row[7],
                updated_at=row[8],
            )
            for row in rows
        ]

    def list_all(self) -> list[DirectoryRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT dir_id, last_seen_path, signature_hash, state,
                       pinned_provider, pinned_release_id, pinned_confidence,
                       created_at, updated_at
                FROM directories
                """
            ).fetchall()

        return [
            DirectoryRecord(
                dir_id=row[0],
                last_seen_path=Path(row[1]),
                signature_hash=row[2],
                state=DirectoryState(row[3]),
                pinned_provider=row[4],
                pinned_release_id=row[5],
                pinned_confidence=row[6],
                created_at=row[7],
                updated_at=row[8],
            )
            for row in rows
        ]

    def get(self, dir_id: str) -> Optional[DirectoryRecord]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT dir_id, last_seen_path, signature_hash, state,
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
            state=DirectoryState(row[3]),
            pinned_provider=row[4],
            pinned_release_id=row[5],
            pinned_confidence=row[6],
            created_at=row[7],
            updated_at=row[8],
        )

    def upsert(self, record: DirectoryRecord) -> DirectoryRecord:
        now = datetime.now().isoformat()
        created_at = record.created_at or now
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO directories (
                    dir_id, last_seen_path, signature_hash, state,
                    pinned_provider, pinned_release_id, pinned_confidence,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.dir_id,
                    str(record.last_seen_path),
                    record.signature_hash,
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
            state=record.state,
            pinned_provider=record.pinned_provider,
            pinned_release_id=record.pinned_release_id,
            pinned_confidence=record.pinned_confidence,
            created_at=created_at,
            updated_at=now,
        )

    def get_or_create(self, dir_id: str, path: Path, signature_hash: str) -> DirectoryRecord:
        existing = self.get(dir_id)
        if not existing:
            record = DirectoryRecord(
                dir_id=dir_id,
                last_seen_path=path,
                signature_hash=signature_hash,
                state=DirectoryState.NEW,
            )
            return self.upsert(record)

        updated = existing
        if existing.signature_hash != signature_hash:
            updated = DirectoryRecord(
                dir_id=existing.dir_id,
                last_seen_path=path,
                signature_hash=signature_hash,
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
            state=DirectoryState.NEW,
            pinned_provider=None,
            pinned_release_id=None,
            pinned_confidence=None,
            created_at=record.created_at,
        )
        return self.upsert(updated)
