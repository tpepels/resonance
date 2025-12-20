"""Integration tests for Applier - transactional execution."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.enricher import build_tag_patch
from resonance.core.identifier import ProviderRelease, ProviderTrack
from resonance.core.planner import Plan, TrackOperation
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from tests.helpers.fs import AudioStubSpec, build_album_dir


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


def _make_plan(source_dir: Path) -> Plan:
    operations = (
        TrackOperation(
            track_position=1,
            source_path=source_dir / "01 - Track A.flac",
            destination_path=Path("Artist/Album/01 - Track A.flac"),
            track_title="Track A",
        ),
        TrackOperation(
            track_position=2,
            source_path=source_dir / "02 - Track B.flac",
            destination_path=Path("Artist/Album/02 - Track B.flac"),
            track_title="Track B",
        ),
    )
    return Plan(
        dir_id="dir-1",
        source_path=source_dir,
        signature_hash="sig-1",
        provider="musicbrainz",
        release_id="mb-123",
        release_title="Album",
        release_artist="Artist",
        destination_path=Path("Artist/Album"),
        operations=operations,
        non_audio_policy="MOVE_WITH_ALBUM",
        plan_version="v1",
        is_compilation=False,
        compilation_reason=None,
        is_classical=False,
    )


def _init_store(tmp_path: Path) -> DirectoryStateStore:
    store = DirectoryStateStore(tmp_path / "state.db")
    record = store.get_or_create("dir-1", Path("/music/album"), "sig-1")
    store.set_state(
        record.dir_id,
        DirectoryState.RESOLVED_AUTO,
        pinned_provider="musicbrainz",
        pinned_release_id="mb-123",
    )
    store.set_state(
        record.dir_id,
        DirectoryState.PLANNED,
        pinned_provider="musicbrainz",
        pinned_release_id="mb-123",
    )
    return store


def test_applier_dry_run_does_not_move_files(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    store = _init_store(tmp_path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=True,
        )
        assert report.status == ApplyStatus.APPLIED
        assert (fixture.path / "01 - Track A.flac").exists()
        assert not (tmp_path / "library/Artist/Album/01 - Track A.flac").exists()
    finally:
        store.close()


def test_applier_moves_and_tags(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    release = _make_release()
    tag_patch = build_tag_patch(plan, release, DirectoryState.RESOLVED_AUTO)
    store = _init_store(tmp_path)
    try:
        report = apply_plan(
            plan,
            tag_patch=tag_patch,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        dest = tmp_path / "library/Artist/Album/01 - Track A.flac"
        assert dest.exists()
        meta = json.loads(dest.with_suffix(dest.suffix + ".meta.json").read_text())
        assert meta["tags"]["album"] == "Album"
        assert meta["tags"]["albumartist"] == "Artist"
        assert meta["tags"]["title"] == "Track A"
        assert meta["tags"]["tracknumber"] == "1"
    finally:
        store.close()


def test_applier_fails_on_collision(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    collision = tmp_path / "library/Artist/Album/01 - Track A.flac"
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.write_text("exists")
    store = _init_store(tmp_path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Destination already exists" in err for err in report.errors)
        assert all("Missing source file" not in err for err in report.errors)
        assert (fixture.path / "01 - Track A.flac").exists()
    finally:
        store.close()


def test_applier_rolls_back_on_move_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    store = _init_store(tmp_path)

    move_calls: list[str] = []
    real_move = shutil.move

    def failing_move(src: str, dest: str) -> str:
        move_calls.append(dest)
        if len(move_calls) == 2:
            raise OSError("boom")
        return real_move(src, dest)

    monkeypatch.setattr("resonance.core.applier.shutil.move", failing_move)

    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert report.rollback_attempted is True
        assert report.rollback_success is True
        assert (fixture.path / "01 - Track A.flac").exists()
        assert not (tmp_path / "library/Artist/Album/01 - Track A.flac").exists()
    finally:
        store.close()


def test_applier_fails_on_tag_patch_mismatch(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    plan = _make_plan(fixture.path)
    release = _make_release()
    tag_patch = build_tag_patch(plan, release, DirectoryState.RESOLVED_AUTO)
    tag_patch = replace(tag_patch, release_id="mb-999")
    store = _init_store(tmp_path)
    try:
        report = apply_plan(
            plan,
            tag_patch=tag_patch,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Tag patch release does not match plan" in err for err in report.errors)
    finally:
        store.close()


def test_applier_noop_on_reapply(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    store = _init_store(tmp_path)
    try:
        first = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert first.status == ApplyStatus.APPLIED
        store.set_state(
            plan.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )
        second = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert second.status == ApplyStatus.NOOP_ALREADY_APPLIED
    finally:
        store.close()


def test_applier_moves_non_audio_with_album(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
        non_audio_files=["cover.jpg"],
    )
    plan = replace(_make_plan(fixture.path), non_audio_policy="MOVE_WITH_ALBUM")
    store = _init_store(tmp_path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        assert not (fixture.path / "cover.jpg").exists()
        assert (tmp_path / "library/Artist/Album/cover.jpg").exists()
    finally:
        store.close()


def test_applier_leaves_non_audio_in_place(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
        non_audio_files=["booklet.pdf"],
    )
    plan = replace(_make_plan(fixture.path), non_audio_policy="LEAVE_IN_PLACE")
    store = _init_store(tmp_path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        assert (fixture.path / "booklet.pdf").exists()
        assert not (tmp_path / "library/Artist/Album/booklet.pdf").exists()
    finally:
        store.close()


def test_applier_skips_tags_when_not_allowed(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    release = _make_release()
    tag_patch = build_tag_patch(plan, release, DirectoryState.RESOLVED_AUTO)
    tag_patch = replace(tag_patch, allowed=False, reason="not_allowed")
    store = _init_store(tmp_path)
    try:
        report = apply_plan(
            plan,
            tag_patch=tag_patch,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        dest = tmp_path / "library/Artist/Album/01 - Track A.flac"
        meta = json.loads(dest.with_suffix(dest.suffix + ".meta.json").read_text())
        assert meta["tags"] == {}
        assert report.tag_ops == ()
    finally:
        store.close()
