"""Integration tests for tag writer backends."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from resonance.core.applier import ApplyStatus, apply_plan
from dataclasses import replace

from resonance.core.enricher import build_tag_patch
from resonance.core.identity.signature import dir_signature
from resonance.core.identifier import ProviderRelease, ProviderTrack
from resonance.core.planner import Plan, TrackOperation
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import MetaJsonTagWriter, MutagenTagWriter, TagWriteResult
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


def _make_release() -> ProviderRelease:
    return ProviderRelease(
        provider="musicbrainz",
        release_id="mb-123",
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="Track A"),),
    )


def test_metajson_tag_writer_apply_and_read(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    plan = _make_plan(fixture.path)
    release = _make_release()
    fixed_now = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    tag_patch = build_tag_patch(
        plan, release, DirectoryState.RESOLVED_AUTO, now_fn=lambda: fixed_now
    )
    writer = MetaJsonTagWriter()

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
            tag_patch=tag_patch,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
            tag_writer=writer,
        )
        assert report.status == ApplyStatus.APPLIED
        dest = tmp_path / "library/Artist/Album/01 - Track A.flac"
        tags = writer.read_tags(dest)
        assert tags["album"] == "Album"
        assert tags["albumartist"] == "Artist"
        assert tags["title"] == "Track A"
        assert tags["tracknumber"] == "1"
        assert tags["resonance.prov.applied_at_utc"] == "2024-01-01T00:00:00Z"
        assert tags["resonance.prov.dir_id"] == plan.dir_id
    finally:
        store.close()


def test_metajson_tag_writer_idempotent(tmp_path: Path) -> None:
    file_path = tmp_path / "track.flac"
    file_path.write_text("stub")
    writer = MetaJsonTagWriter()
    writer.apply_patch(file_path, {"title": "Track A"}, allow_overwrite=False)
    result = writer.apply_patch(file_path, {"title": "Track A"}, allow_overwrite=False)
    assert result.tags_set == ()
    assert result.tags_skipped == ("title",)
    assert writer.read_tags(file_path)["title"] == "Track A"


def test_metajson_provenance_idempotent(tmp_path: Path) -> None:
    file_path = tmp_path / "track.flac"
    file_path.write_text("stub")
    writer = MetaJsonTagWriter()
    tags = {
        "resonance.prov.version": "1",
        "resonance.prov.tool": "resonance",
        "resonance.prov.applied_at_utc": "2024-01-01T00:00:00Z",
    }
    writer.apply_patch(file_path, tags, allow_overwrite=False)
    result = writer.apply_patch(file_path, tags, allow_overwrite=False)
    assert result.tags_set == ()
    assert set(result.tags_skipped) == set(tags.keys())
    stored = writer.read_tags(file_path)
    assert stored["resonance.prov.applied_at_utc"] == "2024-01-01T00:00:00Z"


def test_metajson_respects_overwrite_policy(tmp_path: Path) -> None:
    file_path = tmp_path / "track.flac"
    file_path.write_text("stub")
    writer = MetaJsonTagWriter()
    writer.apply_patch(file_path, {"title": "Original"}, allow_overwrite=True)
    result = writer.apply_patch(file_path, {"title": "New"}, allow_overwrite=False)
    assert result.tags_set == ()
    assert result.tags_skipped == ("title",)
    assert writer.read_tags(file_path)["title"] == "Original"


def test_metajson_allows_overwrite_when_enabled(tmp_path: Path) -> None:
    file_path = tmp_path / "track.flac"
    file_path.write_text("stub")
    writer = MetaJsonTagWriter()
    writer.apply_patch(file_path, {"title": "Original"}, allow_overwrite=True)
    result = writer.apply_patch(file_path, {"title": "New"}, allow_overwrite=True)
    assert result.tags_set == ("title",)
    assert writer.read_tags(file_path)["title"] == "New"


def test_tag_writer_failure_rolls_back_moves(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a")],
    )
    plan = _make_plan(fixture.path)
    release = _make_release()
    tag_patch = build_tag_patch(plan, release, DirectoryState.RESOLVED_AUTO)

    class FailingWriter(MetaJsonTagWriter):
        def apply_patch(self, path: Path, set_tags: dict[str, str], allow_overwrite: bool) -> TagWriteResult:
            raise OSError("boom")

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
            tag_patch=tag_patch,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
            tag_writer=FailingWriter(),
        )
        assert report.status == ApplyStatus.FAILED
        assert report.rollback_attempted is True
        assert (fixture.path / "01 - Track A.flac").exists()
        assert not (tmp_path / "library/Artist/Album/01 - Track A.flac").exists()
        assert not (tmp_path / "library/Artist/Album").exists()
    finally:
        store.close()


def test_apply_does_not_overwrite_existing_tags(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a", tags={"title": "Original"})],
    )
    plan = _make_plan(fixture.path)
    release = _make_release()
    tag_patch = build_tag_patch(plan, release, DirectoryState.RESOLVED_AUTO)

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
            tag_patch=tag_patch,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
            tag_writer=MetaJsonTagWriter(),
        )
        assert report.status == ApplyStatus.APPLIED
        dest = tmp_path / "library/Artist/Album/01 - Track A.flac"
        tags = MetaJsonTagWriter().read_tags(dest)
        assert tags["title"] == "Original"
        assert report.tag_ops
        assert "title" in report.tag_ops[0].tags_skipped
        assert "resonance.prov.overwrote_keys" not in tags
        assert ("title", "Original") in report.tag_ops[0].before_tags
    finally:
        store.close()


def test_apply_overwrite_records_provenance(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a", tags={"title": "Original"})],
    )
    plan = _make_plan(fixture.path)
    release = _make_release()
    tag_patch = build_tag_patch(plan, release, DirectoryState.RESOLVED_AUTO)
    tag_patch = replace(tag_patch, allow_overwrite=True)

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
            tag_patch=tag_patch,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
            tag_writer=MetaJsonTagWriter(),
        )
        assert report.status == ApplyStatus.APPLIED
        dest = tmp_path / "library/Artist/Album/01 - Track A.flac"
        tags = MetaJsonTagWriter().read_tags(dest)
        assert tags["title"] == "Track A"
        assert tags["resonance.prov.overwrote_keys"] == "title"
    finally:
        store.close()


def test_apply_per_field_overwrite_policy(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(
                filename="01 - Track A.flac",
                fingerprint_id="fp-a",
                tags={"title": "Original", "albumartist": "Original Artist"},
            )
        ],
    )
    plan = _make_plan(fixture.path)
    release = _make_release()
    tag_patch = build_tag_patch(plan, release, DirectoryState.RESOLVED_AUTO)
    tag_patch = replace(tag_patch, overwrite_fields=("title",))

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
            tag_patch=tag_patch,
            store=store,
            allowed_roots=(tmp_path / "library",),
            dry_run=False,
            tag_writer=MetaJsonTagWriter(),
        )
        assert report.status == ApplyStatus.APPLIED
        dest = tmp_path / "library/Artist/Album/01 - Track A.flac"
        tags = MetaJsonTagWriter().read_tags(dest)
        assert tags["title"] == "Track A"
        assert tags["albumartist"] == "Original Artist"
        assert "albumartist" in report.tag_ops[0].tags_skipped
        assert tags["resonance.prov.overwrote_keys"] == "title"
    finally:
        store.close()


def test_mutagen_tag_writer_flac_corpus(tmp_path: Path) -> None:
    pytest.importorskip("mutagen")
    corpus_path = Path("tests/fixtures/tag_corpus/flac/corpus.flac")
    flac_path = tmp_path / "corpus.flac"
    flac_path.write_bytes(corpus_path.read_bytes())
    writer = MutagenTagWriter()
    writer.apply_patch(
        flac_path,
        {"title": "Track A", "artist": "Artist", "album": "Album", "albumartist": "Artist"},
        allow_overwrite=True,
    )
    tags = writer.read_tags(flac_path)
    assert tags["title"] == "Track A"
    assert tags["artist"] == "Artist"
    assert tags["album"] == "Album"


def test_mutagen_tag_writer_rejects_unsupported_format(tmp_path: Path) -> None:
    pytest.importorskip("mutagen")
    writer = MutagenTagWriter()
    file_path = tmp_path / "note.txt"
    file_path.write_text("notes")
    with pytest.raises(ValueError, match="Unsupported audio format"):
        writer.read_tags(file_path)
