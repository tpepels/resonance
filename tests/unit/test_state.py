"""Unit tests for directory state records."""

from __future__ import annotations

from pathlib import Path

from resonance.core.state import DirectoryRecord, DirectoryState


class TestDirectoryState:
    def test_all_states_exist(self) -> None:
        expected = {"NEW", "QUEUED_PROMPT", "JAILED", "RESOLVED_AUTO", "RESOLVED_USER", "PLANNED", "APPLIED", "FAILED"}
        assert {s.value for s in DirectoryState} == expected

    def test_is_str_enum(self) -> None:
        assert isinstance(DirectoryState.NEW, str)
        assert DirectoryState.NEW == "NEW"

    def test_from_string(self) -> None:
        assert DirectoryState("PLANNED") is DirectoryState.PLANNED


class TestDirectoryRecord:
    def test_creation_defaults(self) -> None:
        rec = DirectoryRecord(
            dir_id="d-1",
            last_seen_path=Path("/music/album"),
            signature_hash="a" * 64,
            state=DirectoryState.NEW,
        )
        assert rec.dir_id == "d-1"
        assert rec.pinned_provider is None
        assert rec.pinned_release_id is None
        assert rec.signature_version == 1

    def test_frozen(self) -> None:
        rec = DirectoryRecord(
            dir_id="d-1",
            last_seen_path=Path("/music"),
            signature_hash="b" * 64,
            state=DirectoryState.NEW,
        )
        import pytest
        with pytest.raises(AttributeError):
            rec.dir_id = "changed"  # type: ignore[misc]
