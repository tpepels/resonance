"""Unit tests for core models."""

from pathlib import Path
import pytest

from resonance.core.models import TrackInfo, AlbumInfo, parse_int


class TestParseInt:
    """Test the parse_int helper function."""

    def test_parse_none(self):
        """Parse None returns None."""
        assert parse_int(None) is None

    def test_parse_int(self):
        """Parse integer returns same integer."""
        assert parse_int(42) == 42
        assert parse_int(0) == 0
        assert parse_int(-1) == -1

    def test_parse_string_number(self):
        """Parse string number returns integer."""
        assert parse_int("42") == 42
        assert parse_int("0") == 0
        assert parse_int("  42  ") == 42  # With whitespace

    def test_parse_string_fraction(self):
        """Parse track number fraction (e.g., '3/12') returns first part."""
        assert parse_int("3/12") == 3
        assert parse_int("1/10") == 1
        assert parse_int(" 7 / 14 ") == 7

    def test_parse_invalid_string(self):
        """Parse invalid string returns None."""
        assert parse_int("abc") is None
        assert parse_int("") is None
        assert parse_int("  ") is None
        assert parse_int("not-a-number") is None


class TestTrackInfo:
    """Test TrackInfo model."""

    def test_create_minimal(self):
        """Create TrackInfo with minimal data."""
        path = Path("/music/track.flac")
        track = TrackInfo(path=path)

        assert track.path == path
        assert track.title is None
        assert track.artist is None
        assert track.duration_seconds is None

    def test_create_full(self):
        """Create TrackInfo with full data."""
        track = TrackInfo(
            path=Path("/music/track.flac"),
            title="Test Track",
            artist="Test Artist",
            album="Test Album",
            track_number=3,
            duration_seconds=180,
        )

        assert track.title == "Test Track"
        assert track.artist == "Test Artist"
        assert track.album == "Test Album"
        assert track.track_number == 3
        assert track.duration_seconds == 180

    def test_is_classical_detection(self):
        """Test classical music detection."""
        # Has composer and work = classical
        track1 = TrackInfo(
            path=Path("/music/track.flac"),
            composer="Bach",
            work="Goldberg Variations",
        )
        assert track1.is_classical is True

        # Has composer only = classical
        track2 = TrackInfo(
            path=Path("/music/track.flac"),
            composer="Mozart",
        )
        assert track2.is_classical is True

        # No composer = not classical
        track3 = TrackInfo(
            path=Path("/music/track.flac"),
            artist="The Beatles",
        )
        assert track3.is_classical is False


class TestAlbumInfo:
    """Test AlbumInfo model."""

    def test_create_empty(self):
        """Create empty AlbumInfo."""
        album = AlbumInfo(directory=Path("/music/album"))

        assert album.directory == Path("/music/album")
        assert album.tracks == []
        assert album.total_tracks == 0
        assert album.is_classical is False
        assert album.is_uncertain is False

    def test_add_tracks(self):
        """Add tracks to album."""
        album = AlbumInfo(directory=Path("/music/album"))

        track1 = TrackInfo(path=Path("/music/album/01.flac"), title="Track 1")
        track2 = TrackInfo(path=Path("/music/album/02.flac"), title="Track 2")

        album.tracks.append(track1)
        album.tracks.append(track2)
        album.total_tracks = len(album.tracks)

        assert len(album.tracks) == 2
        assert album.total_tracks == 2

    def test_is_classical_detection(self):
        """Test album classical detection (majority of tracks)."""
        album = AlbumInfo(directory=Path("/music/album"))

        # 3 classical tracks
        album.tracks = [
            TrackInfo(path=Path(f"/music/album/{i}.flac"), composer="Bach")
            for i in range(3)
        ]

        # 1 non-classical track
        album.tracks.append(
            TrackInfo(path=Path("/music/album/4.flac"), artist="Pop Artist")
        )

        album.total_tracks = len(album.tracks)

        # 3 out of 4 = 75% > 50% threshold
        assert album.is_classical is True

    def test_destination_path_regular_music(self):
        """Test destination path for regular music."""
        album = AlbumInfo(directory=Path("/music/source"))
        album.canonical_artist = "The Beatles"
        album.canonical_album = "Abbey Road"

        expected = Path("The Beatles") / "Abbey Road"
        assert album.destination_path == expected

    def test_destination_path_classical_single_composer(self):
        """Test destination path for classical with single composer."""
        album = AlbumInfo(directory=Path("/music/source"))
        album.tracks = [
            TrackInfo(path=Path("/music/source/01.flac"), composer="Bach")
        ]
        album.canonical_composer = "Johann Sebastian Bach"
        album.canonical_album = "Goldberg Variations"
        album.canonical_performer = "Glenn Gould"

        expected = Path("Johann Sebastian Bach") / "Goldberg Variations" / "Glenn Gould"
        assert album.destination_path == expected

    def test_destination_path_classical_multiple_composers(self):
        """Test destination path for classical with multiple composers."""
        album = AlbumInfo(directory=Path("/music/source"))
        # Mark as classical but no single composer
        album.tracks = [
            TrackInfo(path=Path("/music/source/01.flac"), composer="Bach"),
            TrackInfo(path=Path("/music/source/02.flac"), composer="Mozart"),
        ]
        album.canonical_composer = None  # Multiple composers
        album.canonical_performer = "Berlin Philharmonic Orchestra"
        album.canonical_album = "Greatest Symphonies"

        expected = Path("Berlin Philharmonic Orchestra") / "Greatest Symphonies"
        assert album.destination_path == expected

    def test_destination_path_compilation(self):
        """Test destination path for compilation (no composer, no performer)."""
        album = AlbumInfo(directory=Path("/music/source"))
        album.tracks = [
            TrackInfo(path=Path("/music/source/01.flac"), composer="Bach"),
            TrackInfo(path=Path("/music/source/02.flac"), composer="Mozart"),
        ]
        album.canonical_composer = None
        album.canonical_performer = None
        album.canonical_album = "100 Best Classical Pieces"

        expected = Path("Various Artists") / "100 Best Classical Pieces"
        assert album.destination_path == expected

    def test_destination_path_missing_info(self):
        """Test destination path returns None when missing required info."""
        album = AlbumInfo(directory=Path("/music/source"))
        album.canonical_artist = "The Beatles"
        # Missing album!

        assert album.destination_path is None


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_album_is_not_classical(self):
        """Empty album is not classical."""
        album = AlbumInfo(directory=Path("/music/album"))
        assert album.is_classical is False

    def test_classical_with_only_composer(self):
        """Classical music with only composer (no album/performer)."""
        album = AlbumInfo(directory=Path("/music/source"))
        album.tracks = [
            TrackInfo(path=Path("/music/source/01.flac"), composer="Bach")
        ]
        album.canonical_composer = "Johann Sebastian Bach"
        # No album or performer

        expected = Path("Johann Sebastian Bach")
        assert album.destination_path == expected

    def test_classical_with_composer_and_album_only(self):
        """Classical music with composer and album, no performer."""
        album = AlbumInfo(directory=Path("/music/source"))
        album.tracks = [
            TrackInfo(path=Path("/music/source/01.flac"), composer="Bach")
        ]
        album.canonical_composer = "Johann Sebastian Bach"
        album.canonical_album = "Goldberg Variations"
        # No performer

        expected = Path("Johann Sebastian Bach") / "Goldberg Variations"
        assert album.destination_path == expected
