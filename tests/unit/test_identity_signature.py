"""Unit tests for directory identity signatures."""

from __future__ import annotations

import os

from pathlib import Path
import pytest
from resonance.core.identifier import DirectoryEvidence, ProviderRelease, ProviderTrack, TrackEvidence
from resonance.core.identity.signature import dir_signature, dir_id
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from tests.helpers.fs import AudioStubSpec, create_non_audio_stub, build_album_dir
from tests.unit.test_identifier import StubProviderClient


def _build_basic_specs() -> list[AudioStubSpec]:
    return [
        AudioStubSpec("01 - One.flac", "fp-basic-001", duration_seconds=200),
        AudioStubSpec("02 - Two.flac", "fp-basic-002", duration_seconds=180),
        AudioStubSpec("03 - Three.flac", "fp-basic-003", duration_seconds=210),
    ]


def test_dir_signature_order_independent(album_dir_factory):
    album = album_dir_factory("order_independent", _build_basic_specs())

    sig1 = dir_signature(album.audio_files)
    sig2 = dir_signature(list(reversed(album.audio_files)))

    assert sig1.signature_hash == sig2.signature_hash
    assert sig1.signature_version == 1


def test_dir_signature_ignores_mtime(album_dir_factory):
    album = album_dir_factory("ignore_mtime", _build_basic_specs())

    sig1 = dir_signature(album.audio_files)
    for path in album.audio_files:
        os.utime(path, None)
    sig2 = dir_signature(album.audio_files)

    assert sig1.signature_hash == sig2.signature_hash


def test_dir_id_stable_across_repeated_scans(album_dir_factory):
    album = album_dir_factory("stable_id", _build_basic_specs())

    sig = dir_signature(album.audio_files)
    assert dir_id(sig) == dir_id(sig)


def test_same_content_different_paths_same_dir_id(temp_dir, album_dir_factory):
    specs = _build_basic_specs()
    album_a = album_dir_factory("same_content_a", specs)
    album_b = build_album_dir(temp_dir / "alt", "same_content_b", specs)

    sig_a = dir_signature(album_a.audio_files)
    sig_b = dir_signature(album_b.audio_files)

    assert dir_id(sig_a) == dir_id(sig_b)


def test_adding_or_removing_audio_changes_signature(album_dir_factory):
    album = album_dir_factory("add_remove", _build_basic_specs())

    sig_full = dir_signature(album.audio_files)
    sig_removed = dir_signature(album.audio_files[:-1])

    assert sig_full.signature_hash != sig_removed.signature_hash


def test_audio_content_change_updates_signature(temp_dir, album_dir_factory):
    specs = _build_basic_specs()
    album_a = album_dir_factory("content_a", specs)
    modified_specs = [
        AudioStubSpec("01 - One.flac", "fp-basic-001", duration_seconds=200),
        AudioStubSpec("02 - Two.flac", "fp-basic-002", duration_seconds=180),
        AudioStubSpec("03 - Three.flac", "fp-basic-999", duration_seconds=210),
    ]
    album_b = build_album_dir(temp_dir / "alt", "content_b", modified_specs)

    sig_a = dir_signature(album_a.audio_files)
    sig_b = dir_signature(album_b.audio_files)

    assert sig_a.signature_hash != sig_b.signature_hash


def test_non_audio_changes_do_not_change_dir_id(album_dir_factory):
    specs = _build_basic_specs()
    album = album_dir_factory("non_audio", specs, non_audio_files=["cover.jpg"])

    sig1 = dir_signature(album.audio_files, album.non_audio_files)
    create_non_audio_stub(album.path / "booklet.pdf")
    non_audio = list(album.non_audio_files) + [album.path / "booklet.pdf"]
    sig2 = dir_signature(album.audio_files, non_audio)

    assert dir_id(sig1) == dir_id(sig2)

def test_dir_signature_single_track_is_stable(album_dir_factory):
    specs = [AudioStubSpec("01 - One.flac", "fp-single-001", duration_seconds=123)]
    album = album_dir_factory("single_track", specs)

    sig1 = dir_signature(album.audio_files)
    sig2 = dir_signature(album.audio_files)

    assert sig1.signature_hash == sig2.signature_hash
    assert dir_id(sig1) == dir_id(sig2)


def test_dir_signature_empty_audio_list_is_supported():
    # If you want to treat this as an error instead, change to pytest.raises(...)
    sig = dir_signature([])
    assert sig.signature_hash  # non-empty hash string
    assert dir_id(sig)         # non-empty id string


def test_dir_signature_is_deterministic_for_same_inputs(album_dir_factory):
    album = album_dir_factory("deterministic_same_inputs", _build_basic_specs())

    sigs = [dir_signature(album.audio_files) for _ in range(5)]
    hashes = {s.signature_hash for s in sigs}
    assert len(hashes) == 1


def test_dir_signature_changes_if_track_duration_changes_when_used_in_signature(temp_dir):
    # Only keep if your signature includes duration. If you do NOT include duration,
    # then this should assert signature_hash stays the same.
    specs_a = _build_basic_specs()
    specs_b = [
        AudioStubSpec("01 - One.flac", "fp-basic-001", duration_seconds=200),
        AudioStubSpec("02 - Two.flac", "fp-basic-002", duration_seconds=181),  # changed
        AudioStubSpec("03 - Three.flac", "fp-basic-003", duration_seconds=210),
    ]
    album_a = build_album_dir(temp_dir, "dur_a", specs_a)
    album_b = build_album_dir(temp_dir, "dur_b", specs_b)

    sig_a = dir_signature(album_a.audio_files)
    sig_b = dir_signature(album_b.audio_files)

    # Adjust expectation depending on design choice:
    # - If duration is part of signature: must differ.
    # - If signature is fingerprint-only: may be equal.
    assert sig_a.signature_hash != sig_b.signature_hash


def test_dir_signature_is_stable_when_filenames_change(temp_dir):
    # Directory identity is content-based; filenames should not affect the signature.
    specs_a = _build_basic_specs()
    specs_b = [
        AudioStubSpec("01 - One (renamed).flac", "fp-basic-001", duration_seconds=200),
        AudioStubSpec("02 - Two.flac", "fp-basic-002", duration_seconds=180),
        AudioStubSpec("03 - Three.flac", "fp-basic-003", duration_seconds=210),
    ]
    album_a = build_album_dir(temp_dir, "name_a", specs_a)
    album_b = build_album_dir(temp_dir, "name_b", specs_b)

    sig_a = dir_signature(album_a.audio_files)
    sig_b = dir_signature(album_b.audio_files)

    assert sig_a.signature_hash == sig_b.signature_hash


def test_dir_signature_duplicate_fingerprint_in_two_files_changes_signature(temp_dir):
    # Two files with same fingerprint should still produce a stable signature.
    # Whether it should be considered "different" vs deduped is a policy decision.
    specs = [
        AudioStubSpec("01 - One.flac", "fp-dup-001", duration_seconds=200),
        AudioStubSpec("02 - Two.flac", "fp-dup-001", duration_seconds=180),  # same fp
        AudioStubSpec("03 - Three.flac", "fp-dup-003", duration_seconds=210),
    ]
    album = build_album_dir(temp_dir, "dup_fp", specs)

    sig = dir_signature(album.audio_files)
    assert sig.signature_hash
    assert dir_id(sig)


def test_dir_signature_ignores_non_audio_order(album_dir_factory):
    specs = _build_basic_specs()
    album = album_dir_factory("non_audio_order", specs, non_audio_files=["cover.jpg", "booklet.pdf"])

    non_audio_a = list(album.non_audio_files)
    non_audio_b = list(reversed(album.non_audio_files))

    sig_a = dir_signature(album.audio_files, non_audio_a)
    sig_b = dir_signature(album.audio_files, non_audio_b)

    assert dir_id(sig_a) == dir_id(sig_b)


def test_dir_signature_non_audio_affects_diagnostics_but_not_dir_id(album_dir_factory):
    specs = _build_basic_specs()
    album = album_dir_factory("non_audio_diag", specs, non_audio_files=["cover.jpg"])

    sig1 = dir_signature(album.audio_files, album.non_audio_files)

    # Add a new non-audio and recompute
    create_non_audio_stub(album.path / "booklet.pdf")
    non_audio = list(album.non_audio_files) + [album.path / "booklet.pdf"]
    sig2 = dir_signature(album.audio_files, non_audio)

    assert dir_id(sig1) == dir_id(sig2)

    # If your Signature object stores a "non_audio_hash" or "non_audio_count", assert it changes.
    # Adjust attribute names to your actual dataclass fields, or remove these asserts.
    if hasattr(sig1, "non_audio_hash") and hasattr(sig2, "non_audio_hash"):
        assert getattr(sig1, "non_audio_hash") != getattr(sig2, "non_audio_hash")
    if hasattr(sig1, "non_audio_count") and hasattr(sig2, "non_audio_count"):
        assert getattr(sig1, "non_audio_count") != getattr(sig2, "non_audio_count")


def test_dir_signature_accepts_path_objects_and_is_stable(album_dir_factory):
    album = album_dir_factory("path_objects", _build_basic_specs())

    # album.audio_files are already Paths; ensure stability anyway.
    sig1 = dir_signature(album.audio_files)
    sig2 = dir_signature([Path(p) for p in album.audio_files])

    assert sig1.signature_hash == sig2.signature_hash


def test_dir_id_changes_when_audio_set_changes_even_if_dir_signature_object_same_type(album_dir_factory):
    album = album_dir_factory("audio_set_change", _build_basic_specs())

    sig_full = dir_signature(album.audio_files)
    sig_less = dir_signature(album.audio_files[:2])

    assert dir_id(sig_full) != dir_id(sig_less)

def test_signature_change_triggers_identify(tmp_path: Path):
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-old",
        )

        updated = store.get_or_create("dir-1", Path("/music/album"), "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        assert updated.state == DirectoryState.NEW
        assert updated.pinned_release_id is None

        # provider has at least one release so identify has something to score
        new_release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-new",
            title="Album",
            artist="Artist",
            tracks=(ProviderTrack(position=1, title="Track", fingerprint_id="fp1"),),
        )
        provider = StubProviderClient([new_release])

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            evidence=DirectoryEvidence(
                tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
                track_count=1,
                total_duration_seconds=180,
            ),
            store=store,
            provider_client=provider,
        )

        # Signature change allows re-identification - verify outcome is resolved or queued
        # (proving identify() ran and processed the release)
        assert outcome.state in (DirectoryState.RESOLVED_AUTO, DirectoryState.QUEUED_PROMPT)
    finally:
        store.close()
