"""Integration tests for filesystem edge cases."""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path

import pytest

from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.identity.signature import dir_signature
from resonance.core.planner import Plan, TrackOperation
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.infrastructure.scanner import LibraryScanner
from tests.helpers.fs import AudioStubSpec, build_album_dir


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


def test_scanner_skips_symlinked_files_integration(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks not supported")
    library = tmp_path / "library"
    library.mkdir(parents=True, exist_ok=True)
    real = library / "track.flac"
    real.write_text("stub")
    link = library / "link.flac"
    try:
        os.symlink(real, link)
    except OSError:
        pytest.skip("symlink creation not permitted")

    scanner = LibraryScanner([library])
    batches = list(scanner.iter_directories())
    assert len(batches) == 1
    assert link not in batches[0].files


def test_scanner_skips_fifo_files(tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir(parents=True, exist_ok=True)
    fifo = library / "stream.flac"
    if not hasattr(os, "mkfifo"):
        pytest.skip("mkfifo not supported")
    try:
        os.mkfifo(fifo)
    except OSError:
        pytest.skip("mkfifo not permitted")
    scanner = LibraryScanner([library])
    assert list(scanner.iter_directories()) == []


def test_applier_detects_case_insensitive_collision(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    plan = _make_plan(fixture.path)
    collision = tmp_path / "library/Artist/Album/01 - track a.flac"
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.write_text("exists")

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create(plan.dir_id, fixture.path, plan.signature_hash)
        store.set_state(
            record.dir_id,
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
            case_insensitive_collisions=True,
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Case-insensitive collision" in err for err in report.errors)
    finally:
        store.close()


def test_applier_cross_device_move_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    real_move = shutil.move
    try:
        record = store.get_or_create(plan.dir_id, fixture.path, plan.signature_hash)
        store.set_state(
            record.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )

        def exdev_move(src: str, dest: str) -> str:
            raise OSError(errno.EXDEV, "Invalid cross-device link")

        monkeypatch.setattr("resonance.core.applier.shutil.move", exdev_move)

        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
        )
        assert report.status == ApplyStatus.APPLIED
        dest = tmp_path / "library/Artist/Album/01 - Track A.flac"
        assert dest.exists()
        assert not (fixture.path / "01 - Track A.flac").exists()
    finally:
        monkeypatch.setattr("resonance.core.applier.shutil.move", real_move)
        store.close()


def test_applier_fails_on_read_only_destination(tmp_path: Path) -> None:
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
    dest_root.chmod(0o500)

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create(plan.dir_id, fixture.path, plan.signature_hash)
        store.set_state(
            record.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=plan.provider,
            pinned_release_id=plan.release_id,
        )
        report = apply_plan(
            plan,
            tag_patch=None,
            store=store,
            allowed_roots=(dest_root,),
            dry_run=False,
        )
        assert report.status == ApplyStatus.FAILED
        assert any("Move failed" in err for err in report.errors)
    finally:
        dest_root.chmod(0o700)
        store.close()


@pytest.mark.skip(reason="scanner merge policy not yet finalized")
def test_scanner_reunites_orphaned_track(tmp_path: Path) -> None:
    """Orphaned track in parent dir should be reunited with siblings."""
    library = tmp_path / "library"
    fixture = build_album_dir(
        library,
        "Album",
        [
            AudioStubSpec(
                filename="01 - Track A.flac",
                fingerprint_id="fp-o-01",
                tags={"album": "Orphan Album", "album_artist": "Artist O"},
            ),
            AudioStubSpec(
                filename="02 - Track B.flac",
                fingerprint_id="fp-o-02",
                tags={"album": "Orphan Album", "album_artist": "Artist O"},
            ),
            AudioStubSpec(
                filename="03 - Track C.flac",
                fingerprint_id="fp-o-03",
                tags={"album": "Orphan Album", "album_artist": "Artist O"},
            ),
        ],
    )
    orphan = fixture.path / "03 - Track C.flac"
    orphan_dest = library / orphan.name
    orphan.rename(orphan_dest)
    sidecar = orphan.with_suffix(orphan.suffix + ".meta.json")
    if sidecar.exists():
        sidecar.rename(orphan_dest.with_suffix(orphan_dest.suffix + ".meta.json"))

    scanner = LibraryScanner([library])
    batches = list(scanner.iter_directories())
    assert len(batches) == 1
    assert len(batches[0].files) == 3


@pytest.mark.skip(reason="scanner merge policy not yet finalized")
def test_scanner_merges_split_album_dirs(tmp_path: Path) -> None:
    """Split album across dirs should be merged into one batch."""
    library = tmp_path / "library"
    build_album_dir(
        library / "old",
        "Album",
        [
            AudioStubSpec(
                filename="01 - Track A.flac",
                fingerprint_id="fp-s-01",
                tags={"album": "Split Album", "album_artist": "Artist S"},
            ),
            AudioStubSpec(
                filename="02 - Track B.flac",
                fingerprint_id="fp-s-02",
                tags={"album": "Split Album", "album_artist": "Artist S"},
            ),
        ],
    )
    build_album_dir(
        library / "new",
        "Album",
        [
            AudioStubSpec(
                filename="03 - Track C.flac",
                fingerprint_id="fp-s-03",
                tags={"album": "Split Album", "album_artist": "Artist S"},
            ),
            AudioStubSpec(
                filename="04 - Track D.flac",
                fingerprint_id="fp-s-04",
                tags={"album": "Split Album", "album_artist": "Artist S"},
            ),
        ],
    )

    scanner = LibraryScanner([library])
    batches = list(scanner.iter_directories())
    assert len(batches) == 1
    assert len(batches[0].files) == 4
