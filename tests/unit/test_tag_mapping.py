from __future__ import annotations

import pytest

from resonance.services.tag_writer import format_tag_keys, normalize_tag_set


def test_normalize_tag_set_collapses_whitespace() -> None:
    tags = {"title": "  Foo\t Bar \n Baz  "}
    normalized = normalize_tag_set(tags)
    assert normalized["title"] == "Foo Bar Baz"


def test_normalize_tag_set_joins_artists() -> None:
    tags = {"artist": ["Artist A", "  Artist   B "]}
    normalized = normalize_tag_set(tags)
    assert normalized["artist"] == "Artist A; Artist B"


def test_normalize_tag_set_preserves_diacritics() -> None:
    tags = {"artist": "Björk"}
    normalized = normalize_tag_set(tags)
    assert normalized["artist"] == "Björk"


def test_normalize_tag_set_rejects_null_bytes() -> None:
    tags = {"title": "Bad\x00Title"}
    with pytest.raises(ValueError, match="null byte"):
        normalize_tag_set(tags)


def test_normalize_tag_set_rejects_overlong_values() -> None:
    tags = {"title": "A" * 1001}
    with pytest.raises(ValueError, match="exceeds 1000"):
        normalize_tag_set(tags)


def test_normalize_tag_set_rejects_invalid_utf8_bytes() -> None:
    tags = {"title": b"\xff"}
    with pytest.raises(ValueError, match="invalid UTF-8"):
        normalize_tag_set(tags)


def test_format_tag_keys_mp3_includes_core_and_mbids() -> None:
    keys = set(format_tag_keys("mp3"))
    expected = {
        "title",
        "artist",
        "album",
        "albumartist",
        "tracknumber",
        "discnumber",
        "musicbrainz_albumid",
        "musicbrainz_recordingid",
    }
    assert expected.issubset(keys)


def test_format_tag_keys_mp4_includes_core_and_mbids() -> None:
    keys = set(format_tag_keys(".m4a"))
    expected = {
        "title",
        "artist",
        "album",
        "albumartist",
        "tracknumber",
        "discnumber",
        "musicbrainz_albumid",
        "musicbrainz_recordingid",
    }
    assert expected.issubset(keys)


def test_format_tag_keys_flac_is_passthrough() -> None:
    assert format_tag_keys("flac") == ()
