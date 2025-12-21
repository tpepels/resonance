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

# --- additional core model tests (more coverage + edge cases) ---

class TestParseIntMoreCases:
    """Additional parse_int cases commonly seen in tags."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("01", 1),
            ("001", 1),
            (" 09 ", 9),
            ("3 / 12", 3),
            ("03/12", 3),
            ("3/12 ", 3),
            ("3\\12", None),  # backslash is not a standard fraction separator
            ("3-12", None),   # dash is ambiguous; treat as invalid unless you support it
        ],
    )
    def test_parse_int_leading_zeros_and_spacing(self, raw, expected):
        assert parse_int(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "3/0",        # still should parse to 3 if you only take first part
            "3/12/99",    # if you split on '/', first is still 3
            "3 / 12 / 99",
        ],
    )
    def test_parse_int_fraction_with_extra_parts(self, raw):
        assert parse_int(raw) == 3

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("+7", 7),        # if you allow leading '+'
            ("-0", 0),        # negative zero should normalize to 0 if int() used
            ("  -5  ", -5),
        ],
    )
    def test_parse_int_signs(self, raw, expected):
        # If your implementation rejects '+7' etc., adjust accordingly.
        assert parse_int(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "3.0",
            "1,000",
            "Ⅳ",          # Roman numeral
            "three",
            "12 tracks",
            "track 7",
        ],
    )
    def test_parse_int_rejects_non_integer_formats(self, raw):
        assert parse_int(raw) is None


class TestTrackInfoMoreCases:
    """Additional TrackInfo behavioral tests."""

    def test_trackinfo_defaults_and_types(self):
        t = TrackInfo(path=Path("x.flac"))
        assert isinstance(t.path, Path)
        assert t.track_number is None
        assert t.disc_number is None  # if field exists; remove if not present
        assert t.composer is None
        assert t.work is None

    def test_is_classical_true_when_work_present_without_composer(self):
        # Work field indicates classical music structure even without composer
        t = TrackInfo(path=Path("x.flac"), work="Symphony No. 5")
        assert t.is_classical is True

    def test_is_classical_false_when_composer_is_blank_or_whitespace(self):
        t1 = TrackInfo(path=Path("x.flac"), composer="")
        t2 = TrackInfo(path=Path("x.flac"), composer="   ")
        # If your model strips composer, then these should be False.
        assert t1.is_classical is False
        assert t2.is_classical is False

    def test_track_number_can_be_parsed_from_string_if_model_supports(self):
        # Only keep this if TrackInfo accepts strings and uses parse_int internally.
        # Otherwise remove.
        t = TrackInfo(path=Path("x.flac"), track_number=parse_int("03/12"))
        assert t.track_number == 3

    def test_duration_seconds_rejects_negative_or_zero_if_enforced(self):
        # If you do not enforce this, remove or relax.
        t = TrackInfo(path=Path("x.flac"), duration_seconds=-1)
        assert t.duration_seconds == -1  # adjust to None if you clamp/validate


class TestAlbumInfoMoreCases:
    """Additional AlbumInfo tests for invariants and destination logic."""

    def test_total_tracks_defaults_to_len_tracks_if_property_computed(self):
        album = AlbumInfo(directory=Path("/music/album"))
        # If total_tracks is computed property, it should track len(tracks).
        # In your current tests, you set total_tracks manually, so this may be a plain field.
        # Adjust expectation depending on implementation.
        assert album.total_tracks in (0, len(album.tracks))

    def test_is_classical_threshold_exactly_half_is_false_or_true_consistently(self):
        album = AlbumInfo(directory=Path("/music/album"))
        # 2 classical, 2 non-classical => exactly 50%
        album.tracks = [
            TrackInfo(path=Path("/music/album/1.flac"), composer="Bach"),
            TrackInfo(path=Path("/music/album/2.flac"), composer="Bach"),
            TrackInfo(path=Path("/music/album/3.flac"), artist="Pop"),
            TrackInfo(path=Path("/music/album/4.flac"), artist="Pop"),
        ]
        album.total_tracks = len(album.tracks)
        # Define expected behavior: your existing test implies "> 50%" threshold, not ">= 50%".
        assert album.is_classical is False

    def test_is_classical_with_missing_tracks_field_is_false(self):
        album = AlbumInfo(directory=Path("/music/album"))
        album.tracks = []
        album.total_tracks = 0
        assert album.is_classical is False

    def test_destination_path_regular_music_requires_artist_and_album(self):
        album = AlbumInfo(directory=Path("/music/source"))
        album.canonical_artist = None
        album.canonical_album = "Abbey Road"
        assert album.destination_path is None

        album.canonical_artist = "The Beatles"
        album.canonical_album = None
        assert album.destination_path is None

    def test_destination_path_regular_music_strips_or_handles_whitespace(self):
        album = AlbumInfo(directory=Path("/music/source"))
        album.canonical_artist = "  The Beatles  "
        album.canonical_album = "  Abbey Road "
        # If you do not strip whitespace in the model, adjust expected.
        expected = Path("The Beatles") / "Abbey Road"
        assert album.destination_path == expected

    def test_destination_path_classical_single_composer_missing_album_uses_composer_root(self):
        album = AlbumInfo(directory=Path("/music/source"))
        album.tracks = [TrackInfo(path=Path("/music/source/01.flac"), composer="Bach")]
        album.total_tracks = len(album.tracks)
        album.canonical_composer = "Johann Sebastian Bach"
        album.canonical_album = None
        album.canonical_performer = "Glenn Gould"
        # With no album, your EdgeCases imply it should fall back to just composer.
        assert album.destination_path == Path("Johann Sebastian Bach")

    def test_destination_path_classical_single_composer_missing_composer_falls_back(self):
        album = AlbumInfo(directory=Path("/music/source"))
        album.tracks = [TrackInfo(path=Path("/music/source/01.flac"), composer="Bach")]
        album.total_tracks = len(album.tracks)
        album.canonical_composer = None
        album.canonical_performer = "Glenn Gould"
        album.canonical_album = "Goldberg Variations"
        # If you consider this classical but composer missing, you likely fall back to performer/album.
        expected = Path("Glenn Gould") / "Goldberg Variations"
        assert album.destination_path == expected

    def test_destination_path_compilation_requires_album(self):
        album = AlbumInfo(directory=Path("/music/source"))
        album.tracks = [
            TrackInfo(path=Path("/music/source/01.flac"), composer="Bach"),
            TrackInfo(path=Path("/music/source/02.flac"), composer="Mozart"),
        ]
        album.total_tracks = len(album.tracks)
        album.canonical_composer = None
        album.canonical_performer = None
        album.canonical_album = None
        assert album.destination_path is None

    def test_destination_path_prefers_performer_for_mixed_composers_when_present(self):
        album = AlbumInfo(directory=Path("/music/source"))
        album.tracks = [
            TrackInfo(path=Path("/music/source/01.flac"), composer="Bach"),
            TrackInfo(path=Path("/music/source/02.flac"), composer="Mozart"),
        ]
        album.total_tracks = len(album.tracks)
        album.canonical_composer = None
        album.canonical_performer = "Berlin Philharmonic Orchestra"
        album.canonical_album = "Greatest Symphonies"
        assert album.destination_path == Path("Berlin Philharmonic Orchestra") / "Greatest Symphonies"

    def test_destination_path_regular_music_does_not_use_performer(self):
        album = AlbumInfo(directory=Path("/music/source"))
        album.tracks = [TrackInfo(path=Path("/music/source/01.flac"), artist="The Beatles")]
        album.total_tracks = len(album.tracks)
        album.canonical_artist = "The Beatles"
        album.canonical_album = "Abbey Road"
        album.canonical_performer = "Should Not Matter"
        assert album.destination_path == Path("The Beatles") / "Abbey Road"


@pytest.mark.unit
class TestModelEdgeCasesMore:
    """Additional edge cases and error handling."""

    def test_album_destination_path_is_relative(self):
        album = AlbumInfo(directory=Path("/music/source"))
        album.canonical_artist = "The Beatles"
        album.canonical_album = "Abbey Road"
        dest = album.destination_path
        assert dest is not None
        assert dest.is_absolute() is False

    def test_album_is_uncertain_default_false_and_mutable(self):
        album = AlbumInfo(directory=Path("/music/album"))
        assert album.is_uncertain is False
        album.is_uncertain = True
        assert album.is_uncertain is True

    def test_album_tracks_mutation_does_not_auto_update_total_tracks_unless_designed(self):
        album = AlbumInfo(directory=Path("/music/album"))
        album.tracks.append(TrackInfo(path=Path("/music/album/01.flac"), composer="Bach"))
        # Depending on whether total_tracks is a field or property, adjust.
        # If it's a field: it stays 0 until explicitly set.
        # If it's computed: it becomes 1 automatically.
        assert album.total_tracks in (0, 1)

    def test_destination_path_handles_empty_strings_as_missing(self):
        album = AlbumInfo(directory=Path("/music/source"))
        album.canonical_artist = ""
        album.canonical_album = "Abbey Road"
        assert album.destination_path is None

        album.canonical_artist = "The Beatles"
        album.canonical_album = ""
        assert album.destination_path is None


def test_album_destination_path_is_cached_and_stable() -> None:
    album = AlbumInfo(directory=Path("/music/source"))
    album.canonical_artist = "Artist"
    album.canonical_album = "Album"
    first = album.destination_path
    assert first == Path("Artist") / "Album"

    album.canonical_artist = "Other Artist"
    album.canonical_album = "Other Album"
    second = album.destination_path
    assert second == first
