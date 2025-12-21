from __future__ import annotations

from pathlib import Path

from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.identifier import ProviderRelease, ProviderTrack
from resonance.core.planner import plan_directory
from resonance.core.state import DirectoryState
from resonance.core.identity.signature import dir_signature
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import MetaJsonTagWriter
from tests.helpers.fs import AudioStubSpec, create_audio_stub


def _init_store(tmp_path: Path, source_dir: Path, signature_hash: str) -> DirectoryStateStore:
    store = DirectoryStateStore(tmp_path / "state.db")
    record = store.get_or_create("dir-layout", source_dir, signature_hash)
    store.set_state(
        record.dir_id,
        DirectoryState.RESOLVED_AUTO,
        pinned_provider="discogs",
        pinned_release_id="dg-layout",
    )
    return store


def test_layout_rules_standard_album(tmp_path: Path) -> None:
    source_dir = tmp_path / "album"
    specs = [
        AudioStubSpec(
            filename="01 - Track A.flac",
            fingerprint_id="fp-layout-01",
            duration_seconds=180,
            tags={"title": "Track A", "artist": "Layout Artist", "album": "Layout Album"},
        ),
    ]
    source_dir.mkdir(parents=True, exist_ok=True)
    audio_files = [create_audio_stub(source_dir / spec.filename, spec) for spec in specs]
    signature_hash = dir_signature(audio_files).signature_hash

    release = ProviderRelease(
        provider="discogs",
        release_id="dg-layout",
        title="Layout Album",
        artist="Layout Artist",
        tracks=(ProviderTrack(position=1, title="Track A"),),
        year=1998,
    )

    store = _init_store(tmp_path, source_dir, signature_hash)
    try:
        plan = plan_directory(
            dir_id="dir-layout",
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

        output_root = tmp_path / "organized"
        report = apply_plan(
            plan,
            None,
            store,
            allowed_roots=(output_root,),
            dry_run=False,
            tag_writer=MetaJsonTagWriter(),
        )

        assert report.status == ApplyStatus.APPLIED
        moved = output_root / "Layout Artist" / "1998 - Layout Album" / "01 - Track A.flac"
        assert moved.exists()
    finally:
        store.close()


def test_layout_rules_multi_disc_prefix(tmp_path: Path) -> None:
    source_dir = tmp_path / "album"
    specs = [
        AudioStubSpec(
            filename="01 - Disc1 Track.flac",
            fingerprint_id="fp-layout-d1",
            duration_seconds=180,
            tags={"title": "Disc1 Track", "artist": "Layout Artist", "album": "Layout Album"},
        ),
        AudioStubSpec(
            filename="01 - Disc2 Track.flac",
            fingerprint_id="fp-layout-d2",
            duration_seconds=181,
            tags={"title": "Disc2 Track", "artist": "Layout Artist", "album": "Layout Album"},
        ),
    ]
    source_dir.mkdir(parents=True, exist_ok=True)
    audio_files = [create_audio_stub(source_dir / spec.filename, spec) for spec in specs]
    signature_hash = dir_signature(audio_files).signature_hash

    release = ProviderRelease(
        provider="discogs",
        release_id="dg-layout",
        title="Layout Album",
        artist="Layout Artist",
        tracks=(
            ProviderTrack(position=1, title="Disc1 Track", disc_number=1),
            ProviderTrack(position=1, title="Disc2 Track", disc_number=2),
        ),
        year=2005,
    )

    store = _init_store(tmp_path, source_dir, signature_hash)
    try:
        plan = plan_directory(
            dir_id="dir-layout",
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

        output_root = tmp_path / "organized"
        report = apply_plan(
            plan,
            None,
            store,
            allowed_roots=(output_root,),
            dry_run=False,
            tag_writer=MetaJsonTagWriter(),
        )

        assert report.status == ApplyStatus.APPLIED
        moved_disc1 = output_root / "Layout Artist" / "2005 - Layout Album" / "01-01 - Disc1 Track.flac"
        moved_disc2 = output_root / "Layout Artist" / "2005 - Layout Album" / "02-01 - Disc2 Track.flac"
        assert moved_disc1.exists()
        assert moved_disc2.exists()
    finally:
        store.close()


def test_layout_rules_classical_uses_composer_root(tmp_path: Path) -> None:
    source_dir = tmp_path / "album"
    specs = [
        AudioStubSpec(
            filename="01 - Symphony.flac",
            fingerprint_id="fp-layout-classical",
            duration_seconds=180,
            tags={"title": "Symphony", "artist": "Orchestra", "album": "Symphonies"},
        ),
    ]
    source_dir.mkdir(parents=True, exist_ok=True)
    audio_files = [create_audio_stub(source_dir / spec.filename, spec) for spec in specs]
    signature_hash = dir_signature(audio_files).signature_hash

    release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-layout",
        title="Symphonies",
        artist="Orchestra",
        tracks=(ProviderTrack(position=1, title="Symphony", composer="Mozart"),),
        year=1788,
    )

    store = _init_store(tmp_path, source_dir, signature_hash)
    try:
        plan = plan_directory(
            dir_id="dir-layout",
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

        output_root = tmp_path / "organized"
        report = apply_plan(
            plan,
            None,
            store,
            allowed_roots=(output_root,),
            dry_run=False,
            tag_writer=MetaJsonTagWriter(),
        )

        assert report.status == ApplyStatus.APPLIED
        moved = output_root / "Mozart" / "1788 - Symphonies" / "01 - Symphony.flac"
        assert moved.exists()
    finally:
        store.close()
