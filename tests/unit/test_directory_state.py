"""Unit tests for directory state persistence and transitions.

These are contract tests for determinism across runs.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


def test_get_or_create_sets_defaults(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/a"), "sig-1")
        assert record.dir_id == "dir-1"
        assert record.last_seen_path == Path("/music/a")
        assert record.signature_hash == "sig-1"
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
        record = store.get_or_create("dir-1", Path("/music/a"), "sig-1")
        record = store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_USER,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
            pinned_confidence=0.9,
        )
        prev_updated_at = record.updated_at

        updated = store.get_or_create("dir-1", Path("/music/b"), "sig-1")
        assert updated.dir_id == record.dir_id
        assert updated.signature_hash == "sig-1"
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
        record = store.get_or_create("dir-1", Path("/music/a"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="discogs",
            pinned_release_id="dg-1",
            pinned_confidence=0.8,
        )

        updated = store.get_or_create("dir-1", Path("/music/a"), "sig-2")
        assert updated.signature_hash == "sig-2"
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
        record = store.get_or_create("dir-1", Path("/music/a"), "sig-1")
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
        record = store.get_or_create("dir-1", Path("/music/a"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_USER,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-1",
            pinned_confidence=0.9,
        )

        unchanged = store.get_or_create("dir-1", Path("/music/a"), "sig-1")
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
        r = store1.get_or_create("dir-1", Path("/music/a"), "sig-1")
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
        r2 = store2.get_or_create("dir-1", Path("/music/a"), "sig-1")
        assert r2.state == DirectoryState.RESOLVED_USER
        assert r2.pinned_provider == "musicbrainz"
        assert r2.pinned_release_id == "mb-1"
    finally:
        store2.close()


def test_path_change_across_reopen_preserves_pin_and_state(tmp_path: Path) -> None:
    """Critical durability test: path change + reopen must preserve pin/state."""
    db = tmp_path / "state.db"

    store1 = DirectoryStateStore(db)
    try:
        r = store1.get_or_create("dir-1", Path("/music/a"), "sig-1")
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
        r2 = store2.get_or_create("dir-1", Path("/music/b"), "sig-1")

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
        record = store.get_or_create("dir-1", Path("/music/a"), "sig-1")

        with pytest.raises(ValueError):
            store.set_state(record.dir_id, DirectoryState.RESOLVED_USER)

        with pytest.raises(ValueError):
            store.set_state(record.dir_id, DirectoryState.RESOLVED_AUTO, pinned_provider="musicbrainz")

        with pytest.raises(ValueError):
            store.set_state(record.dir_id, DirectoryState.RESOLVED_AUTO, pinned_release_id="mb-1")
    finally:
        store.close()
