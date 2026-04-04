"""Unit tests for layout helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from resonance.core.layout import build_album_folder, compute_destination_path
from resonance.core.validation import sanitize_filename


class TestBuildAlbumFolder:
    def test_title_only(self) -> None:
        assert build_album_folder("Abbey Road", include_year=False, sanitize=sanitize_filename) == "Abbey Road"

    def test_with_year(self) -> None:
        assert build_album_folder("Abbey Road", year=1969, include_year=True, sanitize=sanitize_filename) == "1969 - Abbey Road"

    def test_missing_year_uses_0000(self) -> None:
        assert build_album_folder("Album", year=None, include_year=True, sanitize=sanitize_filename) == "0000 - Album"

    def test_none_title_returns_none(self) -> None:
        assert build_album_folder(None, include_year=False, sanitize=sanitize_filename) is None

    def test_empty_title_returns_none(self) -> None:
        assert build_album_folder("", include_year=True, sanitize=sanitize_filename) is None


class TestComputeDestinationPath:
    _DEFAULTS = dict(
        is_classical=False,
        is_compilation=False,
        year=None,
        include_year=False,
        include_performer_subdir=False,
        sanitize=sanitize_filename,
        canonicalize_display=None,
    )

    def test_standard_artist_album(self) -> None:
        result = compute_destination_path(
            album_title="Abbey Road", artist="The Beatles",
            composer=None, performer=None, **self._DEFAULTS,
        )
        assert result == Path("The Beatles/Abbey Road")

    def test_standard_with_year(self) -> None:
        result = compute_destination_path(
            album_title="Abbey Road", artist="The Beatles",
            composer=None, performer=None,
            is_classical=False, is_compilation=False,
            year=1969, include_year=True,
            include_performer_subdir=False,
            sanitize=sanitize_filename, canonicalize_display=None,
        )
        assert result == Path("The Beatles/1969 - Abbey Road")

    def test_compilation(self) -> None:
        result = compute_destination_path(
            album_title="80s Hits", artist=None,
            composer=None, performer=None,
            is_classical=False, is_compilation=True,
            year=None, include_year=False,
            include_performer_subdir=False,
            sanitize=sanitize_filename, canonicalize_display=None,
        )
        assert result == Path("Various Artists/80s Hits")

    def test_classical_composer_album(self) -> None:
        result = compute_destination_path(
            album_title="Symphony No. 5", artist=None,
            composer="Beethoven", performer=None,
            is_classical=True, is_compilation=False,
            year=None, include_year=False,
            include_performer_subdir=False,
            sanitize=sanitize_filename, canonicalize_display=None,
        )
        assert result == Path("Beethoven/Symphony No. 5")

    def test_classical_with_performer_subdir(self) -> None:
        result = compute_destination_path(
            album_title="Symphony No. 5", artist=None,
            composer="Beethoven", performer="Berlin Phil",
            is_classical=True, is_compilation=False,
            year=None, include_year=False,
            include_performer_subdir=True,
            sanitize=sanitize_filename, canonicalize_display=None,
        )
        assert result == Path("Beethoven/Symphony No. 5/Berlin Phil")

    def test_returns_none_when_missing_artist_and_album(self) -> None:
        result = compute_destination_path(
            album_title=None, artist=None,
            composer=None, performer=None, **self._DEFAULTS,
        )
        assert result is None

    def test_canonicalize_display_callback(self) -> None:
        def upper_display(name: str, category: str) -> str:
            return name.upper()

        result = compute_destination_path(
            album_title="Album", artist="artist",
            composer=None, performer=None,
            is_classical=False, is_compilation=False,
            year=None, include_year=False,
            include_performer_subdir=False,
            sanitize=sanitize_filename, canonicalize_display=upper_display,
        )
        assert result == Path("ARTIST/Album")
