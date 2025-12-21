"""Integration tests for Applier - transactional execution."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.enricher import build_tag_patch
from resonance.core.identity.signature import dir_signature
from resonance.core.identifier import ProviderRelease, ProviderTrack
from resonance.core.planner import Plan, TrackOperation, plan_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from tests.helpers.fs import (
    AudioStubSpec,
    build_album_dir,
    create_audio_stub,
    create_non_audio_stub,
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


def _signature_hash(source_dir: Path) -> str:
    audio_files = sorted(source_dir.glob("*.flac"))
    return dir_signature(audio_files).signature_hash


def _make_plan(source_dir: Path) -> Plan:
    signature_hash = _signature_hash(source_dir)
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
        signature_hash=signature_hash,
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


def _init_store(tmp_path: Path, signature_hash: str, source_dir: Path) -> DirectoryStateStore:
    store = DirectoryStateStore(tmp_path / "state.db")
    record = store.get_or_create("dir-1", source_dir, signature_hash)
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
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
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
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
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
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
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


def test_applier_fails_on_signature_mismatch(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        (fixture.path / "01 - Track A.flac").write_text("changed")
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert any(
            "Signature hash mismatch between plan and source directory" in err
            for err in report.errors
        )
    finally:
        store.close()


def test_applier_rejects_path_traversal_in_source_path(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    plan = _make_plan(fixture.path)
    plan = replace(
        plan,
        operations=(
            TrackOperation(
                track_position=1,
                source_path=Path("../evil.flac"),
                destination_path=Path("Artist/Album/01 - Track A.flac"),
                track_title="Track A",
            ),
        ),
    )
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Path traversal not allowed" in err for err in report.errors)
    finally:
        store.close()


def test_applier_rejects_path_traversal_in_destination_path(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    plan = _make_plan(fixture.path)
    plan = replace(
        plan,
        operations=(
            TrackOperation(
                track_position=1,
                source_path=fixture.path / "01 - Track A.flac",
                destination_path=Path("../outside.flac"),
                track_title="Track A",
            ),
        ),
    )
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Path traversal not allowed" in err for err in report.errors)
    finally:
        store.close()


def test_applier_rejects_invalid_dir_id_format(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    plan = replace(_make_plan(fixture.path), dir_id="dir/1")
    store = _init_store(tmp_path, _signature_hash(fixture.path), fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Invalid dir_id format" in err for err in report.errors)
    finally:
        store.close()


def test_applier_rejects_invalid_signature_hash(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    plan = replace(_make_plan(fixture.path), signature_hash="bad-hash")
    store = _init_store(tmp_path, _signature_hash(fixture.path), fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Invalid signature_hash format" in err for err in report.errors)
    finally:
        store.close()


def test_applier_rejects_invalid_release_id_format(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    plan = replace(_make_plan(fixture.path), release_id="mb/123")
    store = _init_store(tmp_path, _signature_hash(fixture.path), fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Invalid release_id format" in err for err in report.errors)
    finally:
        store.close()


def test_applier_detects_partial_completion(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        dest = tmp_path / "library/Artist/Album/01 - Track A.flac"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(fixture.path / "01 - Track A.flac"), str(dest))
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.PARTIAL_COMPLETE
        assert any("Partial completion detected" in err for err in report.errors)
    finally:
        store.close()


def test_applier_rejects_relative_allowed_root(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    plan = _make_plan(fixture.path)
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(Path("relative"),),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Allowed root must be absolute" in err for err in report.errors)
    finally:
        store.close()


def test_applier_fails_on_settings_hash_mismatch(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    plan = replace(_make_plan(fixture.path), settings_hash="settings-1")
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
            settings_hash="settings-2",
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Settings hash mismatch between plan and apply" in err for err in report.errors)
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
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)

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
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
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
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
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


def test_applier_conflict_policy_skip(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    plan = Plan(
        dir_id=plan.dir_id,
        source_path=plan.source_path,
        signature_hash=plan.signature_hash,
        provider=plan.provider,
        release_id=plan.release_id,
        release_title=plan.release_title,
        release_artist=plan.release_artist,
        destination_path=plan.destination_path,
        operations=plan.operations,
        non_audio_policy=plan.non_audio_policy,
        plan_version=plan.plan_version,
        is_compilation=plan.is_compilation,
        compilation_reason=plan.compilation_reason,
        is_classical=plan.is_classical,
        conflict_policy="SKIP",
    )
    collision = tmp_path / "library/Artist/Album/01 - Track A.flac"
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.write_text("exists")
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        assert (tmp_path / "library/Artist/Album/02 - Track B.flac").exists()
        assert (fixture.path / "01 - Track A.flac").exists()
    finally:
        store.close()


def test_applier_conflict_policy_rename(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    plan = Plan(
        dir_id=plan.dir_id,
        source_path=plan.source_path,
        signature_hash=plan.signature_hash,
        provider=plan.provider,
        release_id=plan.release_id,
        release_title=plan.release_title,
        release_artist=plan.release_artist,
        destination_path=plan.destination_path,
        operations=plan.operations,
        non_audio_policy=plan.non_audio_policy,
        plan_version=plan.plan_version,
        is_compilation=plan.is_compilation,
        compilation_reason=plan.compilation_reason,
        is_classical=plan.is_classical,
        conflict_policy="RENAME",
    )
    collision = tmp_path / "library/Artist/Album/01 - Track A.flac"
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.write_text("exists")
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        renamed = tmp_path / "library/Artist/Album/01 - Track A (1).flac"
        assert renamed.exists()
        assert collision.exists()
    finally:
        store.close()


def test_applier_conflict_policy_rename_uses_next_slot(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = replace(_make_plan(fixture.path), conflict_policy="RENAME")
    collision = tmp_path / "library/Artist/Album/01 - Track A.flac"
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.write_text("exists")
    occupied = tmp_path / "library/Artist/Album/01 - Track A (1).flac"
    occupied.write_text("exists")
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        renamed = tmp_path / "library/Artist/Album/01 - Track A (2).flac"
        assert renamed.exists()
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
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
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


def test_applier_moves_multiple_extras_with_album(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
        non_audio_files=["cover.jpg", "booklet.pdf", "disc1.cue", "disc1.log"],
    )
    plan = replace(_make_plan(fixture.path), non_audio_policy="MOVE_WITH_ALBUM")
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        dest_root = tmp_path / "library/Artist/Album"
        for name in ("cover.jpg", "booklet.pdf", "disc1.cue", "disc1.log"):
            assert (dest_root / name).exists()
            assert not (fixture.path / name).exists()
    finally:
        store.close()


def test_applier_moves_unknown_extras_deterministically(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
        non_audio_files=["notes.txt", "readme.nfo"],
    )
    plan = replace(_make_plan(fixture.path), non_audio_policy="MOVE_WITH_ALBUM")
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        dest_root = tmp_path / "library/Artist/Album"
        assert (dest_root / "notes.txt").exists()
        assert (dest_root / "readme.nfo").exists()
        assert not (fixture.path / "notes.txt").exists()
        assert not (fixture.path / "readme.nfo").exists()
    finally:
        store.close()


def test_applier_moves_extras_without_disc_collisions(tmp_path: Path) -> None:
    source_dir = tmp_path / "source" / "album"
    disc1 = source_dir / "Disc 1"
    disc2 = source_dir / "Disc 2"
    audio_files = [
        create_audio_stub(
            disc1 / "01 - Track A.flac",
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
        ),
        create_audio_stub(
            disc2 / "02 - Track B.flac",
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ),
    ]
    create_non_audio_stub(disc1 / "cover.jpg")
    create_non_audio_stub(disc2 / "cover.jpg")

    release = ProviderRelease(
        provider="discogs",
        release_id="dg-extras-disc",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track A", disc_number=1),
            ProviderTrack(position=2, title="Track B", disc_number=2),
        ),
        year=2000,
    )

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        signature_hash = dir_signature(audio_files).signature_hash
        record = store.get_or_create("dir-extras-disc", source_dir, signature_hash)
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="discogs",
            pinned_release_id="dg-extras-disc",
        )

        plan = plan_directory(
            dir_id=record.dir_id,
            store=store,
            pinned_release=release,
            source_files=audio_files,
        )
        store.set_state(
            plan.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )

        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        dest_root = tmp_path / "library/Artist/2000 - Album"
        assert (dest_root / "Disc 1/cover.jpg").exists()
        assert (dest_root / "Disc 2/cover.jpg").exists()
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
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
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
        assert any("Cleanup skipped due to non-audio policy" in warning for warning in report.warnings)
    finally:
        store.close()


def test_applier_deletes_non_audio_and_source_dir(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
        non_audio_files=["notes.txt"],
    )
    plan = replace(_make_plan(fixture.path), non_audio_policy="DELETE")
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
    try:
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        assert not (tmp_path / "library/Artist/Album/notes.txt").exists()
        assert not fixture.path.exists()
        assert report.warnings == ()
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
    store = _init_store(tmp_path, plan.signature_hash, fixture.path)
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
