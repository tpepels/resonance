"""Unit tests for metadata heuristics."""

from __future__ import annotations

from pathlib import Path

from resonance.core.heuristics import guess_metadata_from_path, PathGuess


class TestPathGuess:
    """Test PathGuess functionality."""

    def test_path_guess_creation(self):
        """Test creating a PathGuess."""
        guess = PathGuess(
            artist="Test Artist",
            album="Test Album",
            title="Test Title",
            track_number=1
        )

        assert guess.artist == "Test Artist"
        assert guess.album == "Test Album"
        assert guess.title == "Test Title"
        assert guess.track_number == 1

    def test_path_guess_confidence(self):
        """Test confidence calculation."""
        # Empty guess
        empty_guess = PathGuess()
        assert empty_guess.confidence() == 0.0

        # Partial guess
        partial_guess = PathGuess(artist="Artist", album="Album")
        assert partial_guess.confidence() == 0.5

        # Full guess
        full_guess = PathGuess(
            artist="Artist",
            album="Album",
            title="Title",
            track_number=1
        )
        assert full_guess.confidence() == 1.0


class TestGuessMetadataFromPath:
    """Test metadata guessing from file paths."""

    def test_guess_simple_filename(self):
        """Test guessing from simple filename."""
        path = Path("01 Song Title.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.title == "Song Title"
        assert guess.track_number == 1
        assert guess.artist is None
        assert guess.album is None
        assert guess.confidence() == 0.5

    def test_guess_filename_without_track_number(self):
        """Test guessing from filename without track number."""
        path = Path("Song Title.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.title == "Song Title"
        assert guess.track_number is None
        assert guess.artist is None
        assert guess.album is None
        assert guess.confidence() == 0.25

    def test_guess_with_artist_album_directory(self):
        """Test guessing with Artist - Album directory structure."""
        path = Path("Music/Artist Name/Album Title/01 Track Name.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "Artist Name"
        assert guess.album == "Album Title"
        assert guess.title == "Track Name"
        assert guess.track_number == 1
        assert guess.confidence() == 1.0

    def test_guess_classical_structure(self):
        """Test guessing with classical music directory structure."""
        path = Path("Classical/Beethoven/Symphony No. 5/01 Allegro con brio.flac")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "Beethoven"
        assert guess.album == "Symphony No. 5"
        assert guess.title == "Allegro con brio"
        assert guess.track_number == 1
        assert guess.confidence() == 1.0

    def test_guess_compilation_structure(self):
        """Test guessing with compilation directory structure."""
        path = Path("Compilations/Various Artists/80s Hits/01 Take On Me.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "Various Artists"
        assert guess.album == "80s Hits"
        assert guess.title == "Take On Me"
        assert guess.track_number == 1
        assert guess.confidence() == 1.0

    def test_guess_deep_directory_structure(self):
        """Test guessing with deeper directory structure."""
        path = Path("home/user/Music/Rock/The Beatles/Abbey Road/01 Come Together.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "The Beatles"
        assert guess.album == "Abbey Road"
        assert guess.title == "Come Together"
        assert guess.track_number == 1
        assert guess.confidence() == 1.0

    def test_guess_only_album_directory(self):
        """Test guessing with only album directory."""
        path = Path("Music/Album Title/01 Track.mp3")
        guess = guess_metadata_from_path(path)

        # Algorithm treats first directory level as artist when 3 levels exist
        assert guess.artist == "Music"
        assert guess.album == "Album Title"
        assert guess.title == "Track"
        assert guess.track_number == 1
        assert guess.confidence() == 1.0

    def test_guess_no_directory_structure(self):
        """Test guessing with no directory structure."""
        path = Path("01 Track.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist is None
        assert guess.album is None
        assert guess.title == "Track"
        assert guess.track_number == 1
        assert guess.confidence() == 0.5

    def test_guess_track_number_with_leading_zeros(self):
        """Test guessing with track numbers that have leading zeros."""
        path = Path("Music/Artist/Album/001 Long Track Title.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "Artist"
        assert guess.album == "Album"
        assert guess.title == "Long Track Title"
        assert guess.track_number == 1
        assert guess.confidence() == 1.0

    def test_guess_track_number_three_digits(self):
        """Test guessing with three-digit track numbers."""
        path = Path("Music/Artist/Album/123 Track.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "Artist"
        assert guess.album == "Album"
        assert guess.track_number == 123
        assert guess.title == "Track"
        assert guess.confidence() == 1.0

    def test_guess_special_characters_in_names(self):
        """Test guessing with special characters in names."""
        path = Path("Music/Artist & Artist/Album: Deluxe/01 Track (feat. Other).mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "Artist & Artist"
        assert guess.album == "Album: Deluxe"
        assert guess.title == "Track (feat. Other)"
        assert guess.track_number == 1
        assert guess.confidence() == 1.0

    def test_guess_unicode_characters(self):
        """Test guessing with Unicode characters."""
        path = Path("Music/ Björk /Vespertine/01 Hidden Place.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "Björk"
        assert guess.album == "Vespertine"
        assert guess.title == "Hidden Place"
        assert guess.track_number == 1
        assert guess.confidence() == 1.0

    def test_guess_various_artists_pattern(self):
        """Test guessing with 'Various Artists' pattern."""
        path = Path("Compilations/Various Artists/Greatest Hits/05 Yesterday.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "Various Artists"
        assert guess.album == "Greatest Hits"
        assert guess.title == "Yesterday"
        assert guess.track_number == 5
        assert guess.confidence() == 1.0

    def test_guess_no_track_number_in_filename(self):
        """Test guessing when filename has no track number."""
        path = Path("Music/Artist/Album/Song Title.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "Artist"
        assert guess.album == "Album"
        assert guess.title == "Song Title"
        assert guess.track_number is None
        assert guess.confidence() == 0.75

    def test_guess_empty_filename_parts(self):
        """Test guessing with empty or whitespace filename parts."""
        path = Path("Music/  /Album/01   .mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist is None
        assert guess.album == "Album"
        assert guess.title is None
        assert guess.track_number == 1
        assert guess.confidence() == 0.5

    def test_guess_root_directory_only(self):
        """Test guessing when file is in root directory."""
        path = Path("track.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist is None
        assert guess.album is None
        assert guess.title == "track"
        assert guess.track_number is None
        assert guess.confidence() == 0.25

    def test_guess_different_separators(self):
        """Test guessing with different separator patterns."""
        # Only dash (-) is recognized as separator for Artist - Album pattern
        # Other characters like : and • are treated as part of the album name
        test_cases = [
            ("Artist - Album/01 Track.mp3", "Artist", "Album", "Track", 1),
            ("Artist: Album/01 Track.mp3", "Music", "Artist: Album", "Track", 1),  # : not recognized
            ("Artist • Album/01 Track.mp3", "Music", "Artist • Album", "Track", 1),  # • not recognized
        ]

        for path_str, expected_artist, expected_album, expected_title, expected_track in test_cases:
            path = Path(f"Music/{path_str}")
            guess = guess_metadata_from_path(path)

            assert guess.artist == expected_artist
            assert guess.album == expected_album
            assert guess.title == expected_title
            assert guess.track_number == expected_track

    def test_guess_case_preservation(self):
        """Test that case is preserved in extracted names."""
        path = Path("Music/The BEATLES/Abbey ROAD/01 COME TOGETHER.mp3")
        guess = guess_metadata_from_path(path)

        assert guess.artist == "The BEATLES"
        assert guess.album == "Abbey ROAD"
        assert guess.title == "COME TOGETHER"
        assert guess.track_number == 1

    def test_guess_empty_string_after_cleaning(self):
        """Test that strings that become empty after cleaning return None."""
        # This should exercise the `return cleaned or None` line in _clean
        # We need a case where directory name becomes empty after cleaning
        path = Path("Music/   /01 .mp3")  # Directory name becomes empty after cleaning
        guess = guess_metadata_from_path(path)

        assert guess.artist == "Music"
        assert guess.album is None  # Empty string becomes None
        assert guess.title == "01"   # "01 " becomes "01" after stripping
        assert guess.track_number is None  # No track number pattern matches
