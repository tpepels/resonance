"""Integration tests for crash recovery behavior."""

from __future__ import annotations

import errno
from pathlib import Path
import shutil

from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.enricher import build_tag_patch
from resonance.core.identifier import ProviderRelease, ProviderTrack
from resonance.core.identity.signature import dir_signature
from resonance.core.planner import Plan, TrackOperation
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import TagWriteResult
from tests.helpers.fs import AudioStubSpec, build_album_dir
import pytest


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
        conflict_policy="FAIL",
    )


def test_applier_crash_after_file_moves_before_db_commit(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    dest_root = tmp_path / "library"
    dest_root.mkdir(parents=True, exist_ok=True)

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create(plan.dir_id, fixture.path, plan.signature_hash)
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )
        store.set_state(
            record.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )

        for op in plan.operations:
            dest = dest_root / op.destination_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(op.source_path), str(dest))
            sidecar = op.source_path.with_suffix(op.source_path.suffix + ".meta.json")
            if sidecar.exists():
                shutil.move(
                    str(sidecar),
                    str(dest.with_suffix(dest.suffix + ".meta.json")),
                )

        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(dest_root,),
            dry_run=False,
        )
        assert report.status == ApplyStatus.NOOP_ALREADY_APPLIED
        updated = store.get(plan.dir_id)
        assert updated is not None
        assert updated.state == DirectoryState.APPLIED
    finally:
        store.close()


def test_applier_reports_rollback_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create(plan.dir_id, fixture.path, plan.signature_hash)
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )
        store.set_state(
            record.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )

        fail_on_rollback = {"enabled": False}
        real_move = shutil.move

        def move_with_failure(src: str, dest: str):
            if fail_on_rollback["enabled"] and src.endswith("01 - Track A.flac"):
                raise OSError("rollback failed")
            return real_move(src, dest)

        monkeypatch.setattr("resonance.core.applier.shutil.move", move_with_failure)

        def fail_second_move(src: Path, dest: Path) -> None:
            if dest.name.startswith("02 - Track B"):
                fail_on_rollback["enabled"] = True
                raise OSError("simulated move failure")
            return real_move(str(src), str(dest))

        monkeypatch.setattr("resonance.core.applier._move_file", fail_second_move)

        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert report.rollback_attempted is True
        assert report.rollback_success is False
        assert any("Move failed" in err for err in report.errors)
    finally:
        store.close()


def test_applier_fails_on_tag_write_crash(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track A"),
            ProviderTrack(position=2, title="Track B"),
        ),
    )
    tag_patch = build_tag_patch(plan, release, DirectoryState.RESOLVED_AUTO)

    class _FailingWriter:
        def __init__(self) -> None:
            self.calls = 0

        def read_tags(self, _path: Path) -> dict[str, str]:
            return {}

        def apply_patch(
            self, _path: Path, set_tags: dict[str, str], allow_overwrite: bool
        ):
            self.calls += 1
            if self.calls >= 2:
                raise RuntimeError("tag write crash")
            return TagWriteResult(
                file_path=_path,
                tags_set=tuple(sorted(set_tags.keys())),
                tags_skipped=(),
            )

        def write_tags_exact(self, _path: Path, tags: dict[str, str]) -> None:
            return None

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create(plan.dir_id, fixture.path, plan.signature_hash)
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )
        store.set_state(
            record.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )

        report = apply_plan(
            plan,
            tag_patch=tag_patch,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
            tag_writer=_FailingWriter(),
        )
        assert report.status == ApplyStatus.FAILED
        assert report.rollback_attempted is True
        assert any("Tag write failed" in err for err in report.errors)
    finally:
        store.close()


def test_applier_fails_on_disk_full(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create(plan.dir_id, fixture.path, plan.signature_hash)
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )
        store.set_state(
            record.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )

        def fail_move(_src: Path, _dest: Path) -> None:
            raise OSError(errno.ENOSPC, "No space left on device")

        monkeypatch.setattr("resonance.core.applier._move_file", fail_move)

        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert report.rollback_attempted is True
        assert any("Move failed" in err for err in report.errors)
        assert any("No space left" in err for err in report.errors)
    finally:
        store.close()


def test_applier_fails_on_permission_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create(plan.dir_id, fixture.path, plan.signature_hash)
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )
        store.set_state(
            record.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )

        def fail_move(_src: Path, _dest: Path) -> None:
            raise OSError(errno.EACCES, "Permission denied")

        monkeypatch.setattr("resonance.core.applier._move_file", fail_move)

        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert report.rollback_attempted is True
        assert any("Move failed" in err for err in report.errors)
        assert any("Permission denied" in err for err in report.errors)
    finally:
        store.close()
