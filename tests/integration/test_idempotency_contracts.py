"""Integration tests for idempotency contracts."""

from __future__ import annotations

from pathlib import Path

from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.identity.signature import dir_signature
from resonance.core.identifier import ProviderRelease, ProviderTrack, TrackEvidence
from resonance.core.planner import Plan, TrackOperation
from resonance.core.resolver import resolve_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
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
    )


def _init_store(
    tmp_path: Path, signature_hash: str, source_dir: Path
) -> DirectoryStateStore:
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


def test_apply_twice_is_noop(tmp_path: Path) -> None:
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
        assert not (fixture.path / "01 - Track A.flac").exists()
        assert (tmp_path / "library/Artist/Album/01 - Track A.flac").exists()
    finally:
        store.close()


def test_manual_rename_repaired_as_noop(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path / "source",
        "album",
        [
            AudioStubSpec(filename="01 - Track A.flac", fingerprint_id="fp-a"),
            AudioStubSpec(filename="02 - Track B.flac", fingerprint_id="fp-b"),
        ],
    )
    for sidecar in fixture.path.glob("*.meta.json"):
        sidecar.unlink()
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

        dest = tmp_path / "library/Artist/Album/01 - Track A.flac"
        renamed = tmp_path / "library/Artist/Album/01 - Track A (manual).flac"
        dest.rename(renamed)

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
        assert renamed.exists()
        assert not dest.exists()
    finally:
        store.close()


def test_resolved_dir_skips_provider_requery(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", tmp_path / "album", "a" * 64)
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
            tracks=(ProviderTrack(position=1, title="Track A"),),
        )

        class ProviderStub:
            def __init__(self, releases):
                self.releases = list(releases)
                self.search_by_fingerprints_calls = 0
                self.search_by_metadata_calls = 0

            def search_by_fingerprints(self, fingerprints):
                self.search_by_fingerprints_calls += 1
                return list(self.releases)

            def search_by_metadata(self, artist, album, track_count):
                self.search_by_metadata_calls += 1
                return list(self.releases)

        provider = ProviderStub([release])
        evidence = (
            TrackEvidence(
                fingerprint_id="fp-1", duration_seconds=180, existing_tags={}
            ),
        )
        outcome = resolve_directory(
            dir_id=record.dir_id,
            path=record.last_seen_path,
            signature_hash=record.signature_hash,
            evidence=evidence,
            store=store,
            provider_client=provider,
        )
        assert outcome.state == DirectoryState.RESOLVED_AUTO
        assert provider.search_by_fingerprints_calls == 0
        assert provider.search_by_metadata_calls == 0
    finally:
        store.close()
