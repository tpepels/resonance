"""Unit tests for the filesystem scanner.

Contract: Scanner is discovery-only and produces DirectoryInfo with:
- deterministic ordering
- audio/non-audio separation
- dir_id/signature derived from audio only (non-audio excluded from identity)
"""

from __future__ import annotations

from pathlib import Path

from resonance.core.identity import dir_signature, dir_id
from resonance.infrastructure.scanner import LibraryScanner
from tests.helpers.fs import AudioStubSpec, build_album_dir, create_non_audio_stub


def _build_specs(prefix: str) -> list[AudioStubSpec]:
    return [
        AudioStubSpec(f"{prefix}-b.flac", f"{prefix}-fp-b", duration_seconds=120),
        AudioStubSpec(f"{prefix}-a.flac", f"{prefix}-fp-a", duration_seconds=130),
    ]


def test_iter_directories_is_deterministic(tmp_path: Path) -> None:
    build_album_dir(tmp_path, "b_album", _build_specs("b"))
    build_album_dir(tmp_path, "a_album", _build_specs("a"))

    scanner = LibraryScanner(roots=[tmp_path])

    first = list(scanner.iter_directories())
    second = list(scanner.iter_directories())

    assert [batch.directory.name for batch in first] == ["a_album", "b_album"]
    assert [batch.directory.name for batch in second] == ["a_album", "b_album"]


def test_collect_directory_includes_non_audio_but_identity_is_audio_only(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        _build_specs("x"),
        non_audio_files=["cover.jpg", "notes.txt"],
    )

    scanner = LibraryScanner(roots=[tmp_path])
    batch = scanner.collect_directory(fixture.path)

    assert batch is not None

    # audio
    assert len(batch.files) == 2
    assert [p.name for p in batch.files] == ["x-a.flac", "x-b.flac"]

    # non-audio
    non_audio_names = [p.name for p in batch.non_audio_files]
    assert "cover.jpg" in non_audio_names
    assert "notes.txt" in non_audio_names

    # Identity must be audio-only
    sig_audio_only = dir_signature(batch.files)
    assert batch.signature_hash == sig_audio_only.signature_hash
    assert batch.dir_id == dir_id(sig_audio_only)


def test_iter_directories_orders_files_and_non_audio(tmp_path: Path) -> None:
    fixture = build_album_dir(
        tmp_path,
        "album",
        _build_specs("x"),
        non_audio_files=["z.pdf", "a.jpg"],
    )

    scanner = LibraryScanner(roots=[tmp_path])
    batch = next(scanner.iter_directories())

    # audio ordering must be stable and sorted
    assert [path.name for path in batch.files] == ["x-a.flac", "x-b.flac"]

    # non-audio ordering must be stable and sorted
    non_audio = [p.name for p in batch.non_audio_files]
    # Note: .meta.json files are created by test helpers for audio metadata
    assert "a.jpg" in non_audio
    assert "z.pdf" in non_audio
    assert non_audio == sorted(non_audio)


def test_non_audio_changes_do_not_change_signature_hash(tmp_path: Path) -> None:
    fixture = build_album_dir(tmp_path, "album", _build_specs("x"), non_audio_files=["a.jpg"])

    scanner = LibraryScanner(roots=[tmp_path])
    batch1 = scanner.collect_directory(fixture.path)
    assert batch1 is not None
    sig1 = batch1.signature_hash
    did1 = batch1.dir_id

    # add a new non-audio file
    create_non_audio_stub(fixture.path / "booklet.pdf")

    batch2 = scanner.collect_directory(fixture.path)
    assert batch2 is not None

    # identity unchanged
    assert batch2.signature_hash == sig1
    assert batch2.dir_id == did1

    # but non-audio list reflects new file
    assert "booklet.pdf" in [p.name for p in batch2.non_audio_files]


def test_collect_directory_skips_non_audio_only(tmp_path: Path) -> None:
    non_audio_dir = tmp_path / "docs_only"
    non_audio_dir.mkdir()
    create_non_audio_stub(non_audio_dir / "readme.txt")

    scanner = LibraryScanner(roots=[tmp_path])
    assert scanner.collect_directory(non_audio_dir) is None


def test_iter_directories_ignores_non_audio_only_dirs(tmp_path: Path) -> None:
    # valid album
    fixture = build_album_dir(tmp_path, "album", _build_specs("x"))

    # non-audio-only directory
    non_audio_dir = tmp_path / "docs_only"
    non_audio_dir.mkdir()
    create_non_audio_stub(non_audio_dir / "readme.txt")

    scanner = LibraryScanner(roots=[tmp_path])

    dirs = list(scanner.iter_directories())
    assert len(dirs) == 1
    assert dirs[0].directory == fixture.path
