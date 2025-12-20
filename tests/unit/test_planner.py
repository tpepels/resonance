"""Unit tests for Planner - deterministic plan generation.

These tests enforce that plans are:
- Only generated for RESOLVED directories
- Byte-identical for identical inputs
- Include all necessary move/tag operations
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from resonance.core.identifier import ProviderRelease, ProviderTrack
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


# -------------------------
# Test helpers
# -------------------------


def _stable_json_plan(plan) -> str:
    """Deterministic JSON serialization for plan comparison."""
    payload = asdict(plan)

    # Convert Path objects to strings for JSON serialization
    def convert_paths(obj):
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {k: convert_paths(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [convert_paths(item) for item in obj]
        return obj

    payload = convert_paths(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


# -------------------------
# Tests A: Planner requires pinned resolution
# -------------------------


def test_planner_refuses_new_state(tmp_path: Path):
    """Planner must refuse to generate plan for NEW directories."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        assert record.state == DirectoryState.NEW

        from resonance.core.planner import plan_directory

        # Planner should refuse or return None/error
        with pytest.raises(ValueError, match="Cannot plan.*NEW"):
            plan_directory(
                dir_id=record.dir_id,
                store=store,
                pinned_release=None,  # No release pinned
            )
    finally:
        store.close()


def test_planner_refuses_queued_prompt(tmp_path: Path):
    """Planner must refuse to generate plan for QUEUED_PROMPT directories."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

        from resonance.core.planner import plan_directory

        with pytest.raises(ValueError, match="Cannot plan.*QUEUED_PROMPT"):
            plan_directory(
                dir_id=record.dir_id,
                store=store,
                pinned_release=None,
            )
    finally:
        store.close()


def test_planner_accepts_resolved_auto(tmp_path: Path):
    """Planner must accept RESOLVED_AUTO directories with pinned release."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
        )

        # Create minimal pinned release
        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Test Album",
            artist="Test Artist",
            tracks=(ProviderTrack(position=1, title="Track 1"),),
        )

        from resonance.core.planner import plan_directory

        # Should succeed (not raise)
        plan = plan_directory(
            dir_id=record.dir_id,
            store=store,
            pinned_release=release,
        )

        assert plan is not None
        assert plan.dir_id == "dir-1"
    finally:
        store.close()


def test_planner_accepts_resolved_user(tmp_path: Path):
    """Planner must accept RESOLVED_USER directories with pinned release."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_USER,
            pinned_provider="discogs",
            pinned_release_id="dg-456",
        )

        release = ProviderRelease(
            provider="discogs",
            release_id="dg-456",
            title="Album",
            artist="Artist",
            tracks=(ProviderTrack(position=1, title="Track"),),
        )

        from resonance.core.planner import plan_directory

        plan = plan_directory(
            dir_id=record.dir_id,
            store=store,
            pinned_release=release,
        )

        assert plan is not None
        assert plan.dir_id == "dir-1"
    finally:
        store.close()


# -------------------------
# Tests B: Byte-identical determinism
# -------------------------


def test_plan_is_byte_identical_for_same_inputs(tmp_path: Path):
    """Plan must be byte-identical when inputs are identical."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
        )

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Test Album",
            artist="Test Artist",
            tracks=(
                ProviderTrack(position=1, title="Track 1"),
                ProviderTrack(position=2, title="Track 2"),
            ),
        )

        from resonance.core.planner import plan_directory

        # Generate plan twice
        plan1 = plan_directory(dir_id=record.dir_id, store=store, pinned_release=release)
        plan2 = plan_directory(dir_id=record.dir_id, store=store, pinned_release=release)

        # Plans must be byte-identical
        json1 = _stable_json_plan(plan1)
        json2 = _stable_json_plan(plan2)
        assert json1 == json2
    finally:
        store.close()


# -------------------------
# Tests C: Path rules
# -------------------------


def test_plan_path_regular_album(tmp_path: Path):
    """Regular album should use Artist/Album path."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
        )

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Dark Side of the Moon",
            artist="Pink Floyd",
            tracks=(ProviderTrack(position=1, title="Speak to Me"),),
        )

        from resonance.core.planner import plan_directory

        plan = plan_directory(dir_id=record.dir_id, store=store, pinned_release=release)

        # Destination should be exactly Artist/Album (as final two path components)
        dest = plan.destination_path
        assert plan.is_compilation is False
        assert plan.compilation_reason is None
        assert dest.parts[-2:] == ("Pink Floyd", "Dark Side of the Moon")
    finally:
        store.close()


def test_plan_path_compilation(tmp_path: Path):
    """Compilation should use Various Artists/Album path."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-comp",
        )

        # Compilation: "Various Artists" as artist (simple detection)
        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-comp",
            title="Now That's What I Call Music!",
            artist="Various Artists",
            tracks=(
                ProviderTrack(position=1, title="Track 1"),
                ProviderTrack(position=2, title="Track 2"),
            ),
        )

        from resonance.core.planner import plan_directory

        plan = plan_directory(dir_id=record.dir_id, store=store, pinned_release=release)

        # Compilation should be exactly Various Artists/Album (as final two path components)
        dest = plan.destination_path
        assert plan.is_compilation is True
        assert plan.compilation_reason == "artist_in_compilation_allowlist"
        assert dest.parts[-2:] == ("Various Artists", "Now That's What I Call Music!")
    finally:
        store.close()


def test_plan_path_classical_single_composer(tmp_path: Path):
    """Classical single-composer release should use Composer/Album path."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-classical",
        )

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-classical",
            title="Symphonies",
            artist="London Symphony Orchestra",
            tracks=(
                ProviderTrack(position=1, title="Symphony No.1", composer="Mozart"),
                ProviderTrack(position=2, title="Symphony No.2", composer="Mozart"),
            ),
        )

        from resonance.core.planner import plan_directory

        plan = plan_directory(dir_id=record.dir_id, store=store, pinned_release=release)
        dest = plan.destination_path
        assert plan.is_classical is True
        assert dest.parts[-2:] == ("Mozart", "Symphonies")
    finally:
        store.close()


def test_plan_path_classical_mixed_composer(tmp_path: Path):
    """Classical mixed-composer release should use PerformerOrAlbumArtist/Album path."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-classical-mixed",
        )

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-classical-mixed",
            title="Piano Works",
            artist="Glenn Gould",
            tracks=(
                ProviderTrack(position=1, title="Partita", composer="Bach"),
                ProviderTrack(position=2, title="Sonata", composer="Mozart"),
            ),
        )

        from resonance.core.planner import plan_directory

        plan = plan_directory(dir_id=record.dir_id, store=store, pinned_release=release)
        dest = plan.destination_path
        assert plan.is_classical is True
        assert dest.parts[-2:] == ("Glenn Gould", "Piano Works")
    finally:
        store.close()


def test_plan_path_canonicalization_applies_to_folder_display_only(tmp_path: Path):
    """Planner should canonicalize folder display names without changing pinned metadata."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-canon",
        )

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-canon",
            title="Abbey Road",
            artist="Beatles, The",
            tracks=(ProviderTrack(position=1, title="Come Together"),),
        )

        def canonicalize_display(value: str, category: str) -> str:
            if category == "artist" and value == "Beatles, The":
                return "The Beatles"
            return value

        from resonance.core.planner import plan_directory

        plan = plan_directory(
            dir_id=record.dir_id,
            store=store,
            pinned_release=release,
            canonicalize_display=canonicalize_display,
        )

        assert plan.destination_path.parts[-2:] == ("The Beatles", "Abbey Road")
        assert plan.release_artist == "Beatles, The"
    finally:
        store.close()


def test_plan_path_not_compilation_for_non_allowlist_artist(tmp_path: Path):
    """Non-allowlist artist should not be treated as compilation."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-regular",
        )

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-regular",
            title="Summer Mix",
            artist="Various Artists & Friends",
            tracks=(ProviderTrack(position=1, title="Track 1"),),
        )

        from resonance.core.planner import plan_directory

        plan = plan_directory(dir_id=record.dir_id, store=store, pinned_release=release)

        dest = plan.destination_path
        assert plan.is_compilation is False
        assert plan.compilation_reason is None
        assert dest.parts[-2:] == ("Various Artists & Friends", "Summer Mix")
    finally:
        store.close()


# -------------------------
# Tests D: Non-audio policy
# -------------------------


def test_plan_non_audio_policy_defaults_to_move_with_album(tmp_path: Path):
    """Plan should default non-audio policy to MOVE_WITH_ALBUM."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
        )

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Album",
            artist="Artist",
            tracks=(ProviderTrack(position=1, title="Track"),),
        )

        from resonance.core.planner import plan_directory

        plan = plan_directory(dir_id=record.dir_id, store=store, pinned_release=release)

        # Non-audio policy should be explicitly encoded
        assert hasattr(plan, "non_audio_policy")
        assert plan.non_audio_policy == "MOVE_WITH_ALBUM"
    finally:
        store.close()


# -------------------------
# Tests E: Stable file ordering
# -------------------------


def test_plan_operations_have_stable_ordering(tmp_path: Path):
    """Plan operations should be in stable, deterministic order."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
        )

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Album",
            artist="Artist",
            tracks=(
                ProviderTrack(position=3, title="Track C"),
                ProviderTrack(position=1, title="Track A"),
                ProviderTrack(position=2, title="Track B"),
            ),
        )

        from resonance.core.planner import plan_directory

        plan = plan_directory(dir_id=record.dir_id, store=store, pinned_release=release)

        assert hasattr(plan, "operations")

        # Operations should be ordered by track position (1, 2, 3)
        positions = [op.track_position for op in plan.operations]
        assert positions == [1, 2, 3]

        # Destination filenames should reflect ordering and formatting
        dest_names = [op.destination_path.name for op in plan.operations]
        assert dest_names == [
            "01 - Track A.flac",
            "02 - Track B.flac",
            "03 - Track C.flac",
        ]
    finally:
        store.close()


def test_sanitize_filename_removes_forbidden_chars() -> None:
    from resonance.core.planner import sanitize_filename

    name = 'A/B\\C:D*E?F"G<H>I|J'
    assert sanitize_filename(name) == "A B C D E F G H I J"


def test_sanitize_filename_trims_and_collapses_whitespace() -> None:
    from resonance.core.planner import sanitize_filename

    name = "  A   B   C  "
    assert sanitize_filename(name) == "A B C"


def test_sanitize_filename_handles_reserved_names() -> None:
    from resonance.core.planner import sanitize_filename

    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("prn") == "_prn"
    assert sanitize_filename("LPT1") == "_LPT1"


def test_plan_conflict_policy_default_is_fail(tmp_path: Path):
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
        )

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Album",
            artist="Artist",
            tracks=(ProviderTrack(position=1, title="Track"),),
        )

        from resonance.core.planner import plan_directory

        plan = plan_directory(dir_id=record.dir_id, store=store, pinned_release=release)
        assert plan.conflict_policy == "FAIL"
    finally:
        store.close()
