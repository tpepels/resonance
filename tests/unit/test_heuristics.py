"""Unit tests for metadata heuristics."""

from __future__ import annotations

from pathlib import Path

import pytest

from resonance.core.heuristics import guess_metadata_from_path, PathGuess


class TestPathGuess:
    """Test PathGuess functionality."""

    def test_path_guess_creation(self):
        guess = PathGuess(
            artist="Test Artist",
            album="Test Album",
            title="Test Title",
            track_number=1,
        )
        assert guess.artist == "Test Artist"
        assert guess.album == "Test Album"
        assert guess.title == "Test Title"
        assert guess.track_number == 1

    def test_path_guess_confidence(self):
        assert PathGuess().confidence() == 0.0
        assert PathGuess(artist="Artist", album="Album").confidence() == 0.5
        assert PathGuess(artist="A", album="B", title="C", track_number=1).confidence() == 1.0


class TestGuessMetadataFromPath:
    """Test metadata guessing from file paths."""

    @pytest.mark.parametrize(
        "path_str, artist, album, title, track",
        [
            ("Music/Artist Name/Album Title/01 Track Name.mp3", "Artist Name", "Album Title", "Track Name", 1),
            ("Classical/Beethoven/Symphony No. 5/01 Allegro con brio.flac", "Beethoven", "Symphony No. 5", "Allegro con brio", 1),
            ("Compilations/Various Artists/80s Hits/01 Take On Me.mp3", "Various Artists", "80s Hits", "Take On Me", 1),
            ("home/user/Music/Rock/The Beatles/Abbey Road/01 Come Together.mp3", "The Beatles", "Abbey Road", "Come Together", 1),
            ("Music/Album Title/01 Track.mp3", "Music", "Album Title", "Track", 1),
            ("Music/Artist/Album/001 Long Track Title.mp3", "Artist", "Album", "Long Track Title", 1),
            ("Music/Artist/Album/123 Track.mp3", "Artist", "Album", "Track", 123),
            ("Music/Artist & Artist/Album: Deluxe/01 Track (feat. Other).mp3", "Artist & Artist", "Album: Deluxe", "Track (feat. Other)", 1),
            ("Music/ Björk /Vespertine/01 Hidden Place.mp3", "Björk", "Vespertine", "Hidden Place", 1),
            ("Compilations/Various Artists/Greatest Hits/05 Yesterday.mp3", "Various Artists", "Greatest Hits", "Yesterday", 5),
            ("Music/The BEATLES/Abbey ROAD/01 COME TOGETHER.mp3", "The BEATLES", "Abbey ROAD", "COME TOGETHER", 1),
            # Separator variants: only dash splits Artist - Album
            ("Music/Artist - Album/01 Track.mp3", "Artist", "Album", "Track", 1),
            ("Music/Artist: Album/01 Track.mp3", "Music", "Artist: Album", "Track", 1),
            ("Music/Artist • Album/01 Track.mp3", "Music", "Artist • Album", "Track", 1),
        ],
        ids=[
            "standard", "classical", "compilation", "deep_dirs", "album_only",
            "leading_zeros", "three_digit_track", "special_chars", "unicode",
            "various_artists", "case_preservation",
            "dash_separator", "colon_not_separator", "bullet_not_separator",
        ],
    )
    def test_guess_full_metadata(self, path_str, artist, album, title, track):
        """All four fields present → confidence 1.0."""
        guess = guess_metadata_from_path(Path(path_str))
        assert guess.artist == artist
        assert guess.album == album
        assert guess.title == title
        assert guess.track_number == track
        assert guess.confidence() == 1.0

    @pytest.mark.parametrize(
        "path_str, artist, album, title, track, confidence",
        [
            ("01 Song Title.mp3", None, None, "Song Title", 1, 0.5),
            ("Song Title.mp3", None, None, "Song Title", None, 0.25),
            ("01 Track.mp3", None, None, "Track", 1, 0.5),
            ("track.mp3", None, None, "track", None, 0.25),
            ("Music/Artist/Album/Song Title.mp3", "Artist", "Album", "Song Title", None, 0.75),
        ],
        ids=["with_track", "title_only", "bare_track", "root_file", "no_track_in_dir"],
    )
    def test_guess_partial_metadata(self, path_str, artist, album, title, track, confidence):
        """Some fields missing → confidence < 1.0."""
        guess = guess_metadata_from_path(Path(path_str))
        assert guess.artist == artist
        assert guess.album == album
        assert guess.title == title
        assert guess.track_number == track
        assert guess.confidence() == confidence

    @pytest.mark.parametrize(
        "path_str, artist, album, title, track, confidence",
        [
            ("Music/  /Album/01   .mp3", None, "Album", None, 1, 0.5),
            ("Music/   /01 .mp3", "Music", None, "01", None, 0.5),
        ],
        ids=["empty_artist_and_title", "empty_album_cleaning"],
    )
    def test_guess_edge_cases(self, path_str, artist, album, title, track, confidence):
        """Whitespace-only names cleaned to None."""
        guess = guess_metadata_from_path(Path(path_str))
        assert guess.artist == artist
        assert guess.album == album
        assert guess.title == title
        assert guess.track_number == track
        assert guess.confidence() == confidence
