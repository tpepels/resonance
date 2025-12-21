"""Unit tests for directory state persistence and transitions.

These are contract tests for determinism across runs.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import logging
import os
import sqlite3
import pytest

from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


def _sig(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_get_or_create_sets_defaults(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert record.dir_id == "dir-1"
        assert record.last_seen_path == Path("/music/a")
        assert record.signature_hash == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        assert record.state == DirectoryState.NEW

        assert record.pinned_provider is None
        assert record.pinned_release_id is None
        assert record.pinned_confidence is None

        assert record.created_at
        assert record.updated_at
    finally:
        store.close()


def test_path_change_updates_last_seen_path_only(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        record = store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_USER,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
            pinned_confidence=0.9,
        )
        prev_updated_at = record.updated_at

        updated = store.get_or_create("dir-1", Path("/music/b"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert updated.dir_id == record.dir_id
        assert updated.signature_hash == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        assert updated.state == DirectoryState.RESOLVED_USER

        # Pin unchanged
        assert updated.pinned_provider == "musicbrainz"
        assert updated.pinned_release_id == "mb-1"
        assert updated.pinned_confidence == pytest.approx(0.9)

        # Only path changed
        assert updated.last_seen_path == Path("/music/b")

        # Timestamp should not go backwards
        assert updated.updated_at >= prev_updated_at
    finally:
        store.close()


def test_signature_change_resets_state_and_clears_pinned(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="discogs",
            pinned_release_id="dg-1",
            pinned_confidence=0.8,
        )

        updated = store.get_or_create("dir-1", Path("/music/a"), "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        assert updated.signature_hash == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        assert updated.state == DirectoryState.NEW

        # Pin cleared completely (not just release_id)
        assert updated.pinned_provider is None
        assert updated.pinned_release_id is None
        assert updated.pinned_confidence is None
    finally:
        store.close()


def test_unjail_resets_state_to_new_and_clears_pinned(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.JAILED,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
            pinned_confidence=0.5,
        )

        updated = store.unjail(record.dir_id)
        assert updated.state == DirectoryState.NEW
        assert updated.pinned_provider is None
        assert updated.pinned_release_id is None
        assert updated.pinned_confidence is None
    finally:
        store.close()


def test_pinned_release_reused_when_signature_unchanged(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_USER,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
            pinned_confidence=0.9,
        )

        unchanged = store.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert unchanged.state == DirectoryState.RESOLVED_USER
        assert unchanged.pinned_provider == "musicbrainz"
        assert unchanged.pinned_release_id == "mb-1"
        assert unchanged.pinned_confidence == pytest.approx(0.9)
    finally:
        store.close()


def test_state_is_persisted_across_store_instances(tmp_path: Path) -> None:
    db = tmp_path / "state.db"

    store1 = DirectoryStateStore(db)
    try:
        r = store1.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store1.set_state(
            r.dir_id,
            DirectoryState.RESOLVED_USER,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
            pinned_confidence=0.9,
        )
    finally:
        store1.close()

    store2 = DirectoryStateStore(db)
    try:
        r2 = store2.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert r2.state == DirectoryState.RESOLVED_USER
        assert r2.pinned_provider == "musicbrainz"
        assert r2.pinned_release_id == "mb-1"
    finally:
        store2.close()


def test_directory_store_orders_list_by_state(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        for dir_id in ["c", "a", "b"]:
            record = store.get_or_create(
                dir_id, Path(f"/music/{dir_id}"), _sig(dir_id)
            )
            store.set_state(
                record.dir_id,
                DirectoryState.RESOLVED_AUTO,
                pinned_provider="musicbrainz",
                pinned_release_id=f"mb-{dir_id}",
            )

        records = store.list_by_state(DirectoryState.RESOLVED_AUTO)
        again = store.list_by_state(DirectoryState.RESOLVED_AUTO)
        assert [record.dir_id for record in records] == ["a", "b", "c"]
        assert [record.dir_id for record in again] == ["a", "b", "c"]
    finally:
        store.close()


def test_directory_store_orders_list_all(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        for dir_id in ["c", "a", "b"]:
            store.get_or_create(dir_id, Path(f"/music/{dir_id}"), _sig(dir_id))

        records = store.list_all()
        assert [record.dir_id for record in records] == ["a", "b", "c"]
    finally:
        store.close()


def test_path_change_across_reopen_preserves_pin_and_state(tmp_path: Path) -> None:
    """Critical durability test: path change + reopen must preserve pin/state."""
    db = tmp_path / "state.db"

    store1 = DirectoryStateStore(db)
    try:
        r = store1.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store1.set_state(
            r.dir_id,
            DirectoryState.RESOLVED_USER,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
            pinned_confidence=0.9,
        )
    finally:
        store1.close()

    # Reopen and call get_or_create with new path but same signature
    store2 = DirectoryStateStore(db)
    try:
        r2 = store2.get_or_create("dir-1", Path("/music/b"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        # Must preserve state and pin
        assert r2.state == DirectoryState.RESOLVED_USER
        assert r2.pinned_provider == "musicbrainz"
        assert r2.pinned_release_id == "mb-1"
        assert r2.pinned_confidence == pytest.approx(0.9)

        # Must update path
        assert r2.last_seen_path == Path("/music/b")
    finally:
        store2.close()


def test_resolved_state_requires_provider_and_release_id(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        with pytest.raises(ValueError):
            store.set_state(record.dir_id, DirectoryState.RESOLVED_USER)

        with pytest.raises(ValueError):
            store.set_state(record.dir_id, DirectoryState.RESOLVED_AUTO, pinned_provider="musicbrainz")

        with pytest.raises(ValueError):
            store.set_state(record.dir_id, DirectoryState.RESOLVED_AUTO, pinned_release_id="mb-1")
    finally:
        store.close()


def test_schema_metadata_initialized(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        conn = sqlite3.connect(store.path)
        try:
            version = conn.execute(
                "SELECT value FROM schema_metadata WHERE key = ?",
                ("schema_version",),
            ).fetchone()[0]
        finally:
            conn.close()
        assert version == "4"
    finally:
        store.close()


def test_schema_missing_metadata_with_existing_rows_raises(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            CREATE TABLE directories (
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
        conn.execute(
            "INSERT INTO directories (dir_id, last_seen_path, signature_hash, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("dir-1", "/music/a", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "NEW", "now", "now"),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(ValueError, match="missing schema_version"):
        DirectoryStateStore(db).close()


def test_signature_version_change_resets_state(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create(
            "dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", signature_version=1
        )
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
        )

        updated = store.get_or_create(
            "dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", signature_version=2
        )
        assert updated.state == DirectoryState.NEW
        assert updated.pinned_provider is None
        assert updated.pinned_release_id is None
        assert updated.signature_version == 2
    finally:
        store.close()


def test_signature_version_change_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create(
            "dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", signature_version=1
        )
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
        )

        with caplog.at_level(logging.WARNING):
            store.get_or_create(
                "dir-1",
                Path("/music/a"),
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                signature_version=2,
            )
        assert "Signature algorithm changed" in caplog.text
    finally:
        store.close()


def test_directory_store_rejects_concurrent_version(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            CREATE TABLE schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_metadata (key, value) VALUES (?, ?)",
            ("schema_version", "4"),
        )
        conn.execute(
            "INSERT INTO schema_metadata (key, value) VALUES (?, ?)",
            ("active_app_version", "0.1.0"),
        )
        conn.execute(
            "INSERT INTO schema_metadata (key, value) VALUES (?, ?)",
            ("active_app_pid", str(os.getpid())),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(ValueError, match="already in use"):
        DirectoryStateStore(db, app_version="0.2.0").close()


def test_directory_store_rejects_future_schema_version(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            CREATE TABLE schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_metadata (key, value) VALUES (?, ?)",
            ("schema_version", "99"),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(ValueError, match=r"DB schema 99 > supported 4"):
        DirectoryStateStore(db).close()


def test_schema_migration_from_v1_preserves_records(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            CREATE TABLE schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_metadata (key, value) VALUES (?, ?)",
            ("schema_version", "1"),
        )
        conn.execute(
            """
            CREATE TABLE directories (
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
        conn.execute(
            "INSERT INTO directories (dir_id, last_seen_path, signature_hash, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("dir-1", "/music/a", "a" * 64, "NEW", "now", "now"),
        )
        conn.commit()
    finally:
        conn.close()

    store = DirectoryStateStore(db)
    try:
        record = store.get("dir-1")
        assert record is not None
        assert record.signature_version == 1
        conn = sqlite3.connect(db)
        try:
            version = conn.execute(
                "SELECT value FROM schema_metadata WHERE key = ?",
                ("schema_version",),
            ).fetchone()[0]
        finally:
            conn.close()
        assert version == "4"
    finally:
        store.close()


def test_schema_migration_from_v3_preserves_records(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            CREATE TABLE schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_metadata (key, value) VALUES (?, ?)",
            ("schema_version", "3"),
        )
        conn.execute(
            """
            CREATE TABLE directories (
                dir_id TEXT PRIMARY KEY,
                last_seen_path TEXT NOT NULL,
                signature_hash TEXT NOT NULL,
                signature_version INTEGER NOT NULL DEFAULT 1,
                state TEXT NOT NULL,
                pinned_provider TEXT,
                pinned_release_id TEXT,
                pinned_confidence REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO directories (dir_id, last_seen_path, signature_hash, signature_version, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("dir-1", "/music/a", "a" * 64, 1, "NEW", "now", "now"),
        )
        conn.commit()
    finally:
        conn.close()

    store = DirectoryStateStore(db)
    try:
        record = store.get("dir-1")
        assert record is not None
        assert record.signature_hash == "a" * 64
        version = store._get_metadata("schema_version")
        assert version == "4"
    finally:
        store.close()
