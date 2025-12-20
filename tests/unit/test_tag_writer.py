"""Unit tests for TagWriter abstraction and backend selection."""

from __future__ import annotations

import pytest

from resonance.services import tag_writer


def test_tag_snapshot_is_hashable_and_sorted_keys() -> None:
    snapshot = tag_writer.TagSnapshot.from_tags(
        {"artist": "Artist", "title": "Track", "album": "Album"}
    )
    assert snapshot.tags == (
        ("album", "Album"),
        ("artist", "Artist"),
        ("title", "Track"),
    )


def test_get_tag_writer_selects_backend() -> None:
    assert isinstance(tag_writer.get_tag_writer("meta-json"), tag_writer.MetaJsonTagWriter)
    assert isinstance(tag_writer.get_tag_writer("mutagen"), tag_writer.MutagenTagWriter)


def test_get_tag_writer_unknown_backend() -> None:
    with pytest.raises(ValueError, match="Unknown tag writer backend"):
        tag_writer.get_tag_writer("nope")
