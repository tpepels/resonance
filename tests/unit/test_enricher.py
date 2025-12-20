"""Unit tests for Enricher - deterministic tag patch generation."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from datetime import datetime, timezone

from resonance.core.enricher import build_tag_patch
from resonance import __version__
from resonance.core.identifier import ProviderRelease, ProviderTrack
from resonance.core.planner import Plan, TrackOperation
from resonance.core.state import DirectoryState


def _stable_json_patch(patch) -> str:
    payload = asdict(patch)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _make_plan() -> Plan:
    operations = (
        TrackOperation(
            track_position=2,
            source_path=Path("source_2.flac"),
            destination_path=Path("dest/02 - Track B.flac"),
            track_title="Track B",
        ),
        TrackOperation(
            track_position=1,
            source_path=Path("source_1.flac"),
            destination_path=Path("dest/01 - Track A.flac"),
            track_title="Track A",
        ),
    )
    return Plan(
        dir_id="dir-1",
        source_path=Path("/music/album"),
        signature_hash="sig-1",
        provider="musicbrainz",
        release_id="mb-123",
        release_title="Album",
        release_artist="Artist",
        destination_path=Path("Artist/Album"),
        operations=tuple(sorted(operations, key=lambda op: op.track_position)),
        non_audio_policy="MOVE_WITH_ALBUM",
        plan_version="v1",
        is_compilation=False,
        compilation_reason=None,
        is_classical=False,
    )


def _make_release() -> ProviderRelease:
    return ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track A"),
            ProviderTrack(position=2, title="Track B"),
        ),
    )


@pytest.mark.parametrize(
    "state",
    [DirectoryState.NEW, DirectoryState.QUEUED_PROMPT, DirectoryState.JAILED],
)
def test_enricher_refuses_unresolved_states(state: DirectoryState) -> None:
    plan = _make_plan()
    release = _make_release()

    patch = build_tag_patch(plan, release, state)

    assert patch.allowed is False
    assert patch.reason == "state_not_resolved"
    assert patch.album_patch is None
    assert patch.track_patches == ()


def test_enricher_refuses_resolved_user_by_default() -> None:
    plan = _make_plan()
    release = _make_release()

    patch = build_tag_patch(plan, release, DirectoryState.RESOLVED_USER)

    assert patch.allowed is False
    assert patch.reason == "user_resolved_not_allowed"
    assert patch.album_patch is None
    assert patch.track_patches == ()


def test_enricher_builds_patch_for_resolved_auto() -> None:
    plan = _make_plan()
    release = _make_release()

    fixed_now = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    patch = build_tag_patch(
        plan, release, DirectoryState.RESOLVED_AUTO, now_fn=lambda: fixed_now
    )

    assert patch.allowed is True
    assert patch.album_patch is not None
    assert patch.album_patch.set_tags == {
        "album": "Album",
        "albumartist": "Artist",
    }
    assert [tp.track_position for tp in patch.track_patches] == [1, 2]
    assert [tp.set_tags["title"] for tp in patch.track_patches] == [
        "Track A",
        "Track B",
    ]
    assert [tp.set_tags["tracknumber"] for tp in patch.track_patches] == ["1", "2"]
    assert patch.provenance_tags["resonance.prov.tool"] == "resonance"
    assert patch.provenance_tags["resonance.prov.tool_version"] == __version__
    assert patch.provenance_tags["resonance.prov.dir_id"] == plan.dir_id
    assert patch.provenance_tags["resonance.prov.pinned_release_id"] == release.release_id
    assert patch.provenance_tags["resonance.prov.applied_at_utc"] == "2024-01-01T00:00:00Z"


def test_enricher_orders_patches_by_track_position() -> None:
    operations = (
        TrackOperation(
            track_position=2,
            source_path=Path("source_2.flac"),
            destination_path=Path("dest/02 - Track B.flac"),
            track_title="Track B",
        ),
        TrackOperation(
            track_position=1,
            source_path=Path("source_1.flac"),
            destination_path=Path("dest/01 - Track A.flac"),
            track_title="Track A",
        ),
    )
    plan = _make_plan()
    plan = Plan(
        dir_id=plan.dir_id,
        source_path=plan.source_path,
        signature_hash=plan.signature_hash,
        provider=plan.provider,
        release_id=plan.release_id,
        release_title=plan.release_title,
        release_artist=plan.release_artist,
        destination_path=plan.destination_path,
        operations=operations,
        non_audio_policy=plan.non_audio_policy,
        plan_version=plan.plan_version,
        is_compilation=plan.is_compilation,
        compilation_reason=plan.compilation_reason,
        is_classical=plan.is_classical,
    )
    release = _make_release()

    patch = build_tag_patch(plan, release, DirectoryState.RESOLVED_AUTO)

    assert [tp.track_position for tp in patch.track_patches] == [1, 2]


def test_enricher_raises_on_missing_track_positions() -> None:
    plan = _make_plan()
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track A"),),
    )

    with pytest.raises(ValueError, match="missing tracks for positions"):
        build_tag_patch(plan, release, DirectoryState.RESOLVED_AUTO)


def test_enricher_is_byte_identical_for_same_inputs() -> None:
    plan = _make_plan()
    release = _make_release()

    fixed_now = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    patch1 = build_tag_patch(
        plan, release, DirectoryState.RESOLVED_AUTO, now_fn=lambda: fixed_now
    )
    patch2 = build_tag_patch(
        plan, release, DirectoryState.RESOLVED_AUTO, now_fn=lambda: fixed_now
    )

    assert _stable_json_patch(patch1) == _stable_json_patch(patch2)
