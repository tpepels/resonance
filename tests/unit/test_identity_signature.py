"""Unit tests for directory identity signatures."""

from __future__ import annotations

import os

from resonance.core.identity.signature import dir_signature, dir_id
from tests.helpers.fs import AudioStubSpec, create_non_audio_stub, build_album_dir


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
