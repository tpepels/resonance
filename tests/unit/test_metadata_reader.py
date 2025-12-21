"""Unit tests for MetadataReader stub metadata handling."""

from __future__ import annotations

from pathlib import Path

from resonance.services.metadata_reader import MetadataReader


def test_stub_metadata_reads_disc_number(
    tmp_path: Path, create_test_audio_file
) -> None:
    file_path = tmp_path / "01 - Track A.flac"
    create_test_audio_file(
        path=file_path,
        title="Track A",
        artist="Artist",
        album="Album",
        track_number=1,
        disc_number=2,
    )
    track = MetadataReader.read_track(file_path)
    assert track.track_number == 1
    assert track.disc_number == 2
