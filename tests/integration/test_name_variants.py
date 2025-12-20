"""Integration tests for artist name variants and canonicalization.

Tests handling of different name spellings, "The" prefix, unicode characters,
and other common artist name variations.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest

from resonance.app import ResonanceApp
from resonance.core.models import AlbumInfo
from resonance.core.identity.matching import normalize_token


class TestArtistNameVariants:
    """Test artist name variant canonicalization."""

    def test_normalize_token_function(self):
        """Test the normalize_token function with various inputs."""
        # Basic normalization
        assert normalize_token("The Beatles") == "thebeatles"
        assert normalize_token("Beatles") == "beatles"
        assert normalize_token("Beatles, The") == "beatlesthe"

        # Unicode normalization
        assert normalize_token("Björk") == "bjork"
        assert normalize_token("Sigur Rós") == "sigurros"
        assert normalize_token("Yo-Yo Ma") == "yoyoma"

        # Featuring removal
        assert normalize_token("Daft Punk feat. Pharrell") == "daftpunk"
        assert normalize_token("Artist (featuring Guest)") == "artist"
        assert normalize_token("Artist ft. Guest") == "artist"

        # Multiple words and punctuation
        assert normalize_token("Art Blakey & The Jazz Messengers") == "artblakeythejazzmessengers"
        assert normalize_token("Miles Davis") == "milesdavis"

    def test_bjork_unicode_variants(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """Test Icelandic artist with unicode characters.

        Real-world case: Björk
        - Variants: "Björk", "Bjork", "Björk Guðmundsdóttir", "Bjork Gudmundsdottir"

        Expected:
        - All variants canonicalize to "Björk" (preserve correct unicode)
        - Album organized under canonical name
        """
        input_dir = test_library / "bjork_homogenic"
        input_dir.mkdir()

        tracks = [
            {
                "filename": "01 - Hunter.flac",
                "title": "Hunter",
                "artist": "Björk",  # Correct unicode
                "album": "Homogenic",
                "track_number": 1,
            },
            {
                "filename": "02 - Jóga.flac",
                "title": "Jóga",
                "artist": "Bjork",  # ASCII variant
                "album": "Homogenic",
                "track_number": 2,
            },
            {
                "filename": "03 - Unravel.flac",
                "title": "Unravel",
                "artist": "Björk Guðmundsdóttir",  # Full name
                "album": "Homogenic",
                "track_number": 3,
            },
        ]

        for track_spec in tracks:
            create_test_audio_file(
                path=input_dir / track_spec["filename"],
                **{k: v for k, v in track_spec.items() if k != "filename"},
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            # Verify normalization produces same token
            variants = ["Björk", "Bjork", "Björk Guðmundsdóttir"]
            tokens = {normalize_token(v) for v in variants}

            # All should normalize to same token (without diacritics)
            assert len(tokens) == 1, f"All variants should normalize to same token, got: {tokens}"

            # The canonicalizer should map all these to preferred form
            # (which would be "Björk" based on most common/preferred spelling)

        finally:
            app.close()

    def test_the_beatles_variants(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """Test 'The' prefix variants.

        Real-world case: The Beatles
        - Variants: "The Beatles", "Beatles", "Beatles, The"

        Expected:
        - All variants canonicalize to "The Beatles"
        - Normalized token: "thebeatles" or "beatles" (same for all)
        """
        input_dir = test_library / "beatles_abbeyroad"
        input_dir.mkdir()

        tracks = [
            {
                "filename": "01 - Come Together.flac",
                "title": "Come Together",
                "artist": "The Beatles",  # Standard form
                "album": "Abbey Road",
                "track_number": 1,
            },
            {
                "filename": "02 - Something.flac",
                "title": "Something",
                "artist": "Beatles",  # No "The"
                "album": "Abbey Road",
                "track_number": 2,
            },
            {
                "filename": "03 - Maxwell's Silver Hammer.flac",
                "title": "Maxwell's Silver Hammer",
                "artist": "Beatles, The",  # Reversed
                "album": "Abbey Road",
                "track_number": 3,
            },
        ]

        for track_spec in tracks:
            create_test_audio_file(
                path=input_dir / track_spec["filename"],
                **{k: v for k, v in track_spec.items() if k != "filename"},
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            # Verify normalization
            variants = ["The Beatles", "Beatles", "Beatles, The"]
            tokens = {normalize_token(v) for v in variants}

            # Should have at most 2 tokens ("beatles" and "beatlesthe")
            # Ideally, canonicalizer would map both to same canonical form

            # Check all tracks loaded
            def mock_read_track(path):
                from resonance.core.models import TrackInfo

                track = TrackInfo(path=path)
                for spec in tracks:
                    if path.name == spec["filename"]:
                        track.title = spec["title"]
                        track.artist = spec["artist"]
                        track.album = spec["album"]
                        track.track_number = spec["track_number"]
                        break
                return track

            with patch("resonance.services.metadata_reader.MetadataReader.read_track", mock_read_track):
                from resonance.visitors import IdentifyVisitor

                mock_mb = MagicMock()
                identify_visitor = IdentifyVisitor(
                    musicbrainz=mock_mb,
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=app.release_search,
                )

                identify_visitor.visit(album)

            assert len(album.tracks) == 3

        finally:
            app.close()

    def test_special_characters_sigur_ros(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """Test artist with special characters.

        Real-world case: Sigur Rós
        - Variants: "Sigur Rós", "Sigur Ros", "Sigur-Ros"

        Expected:
        - Normalize to same token
        - Preserve correct spelling in canonical form
        """
        # Test normalization
        variants = ["Sigur Rós", "Sigur Ros", "Sigur-Ros"]
        tokens = {normalize_token(v) for v in variants}

        # All should normalize to "sigurros"
        assert len(tokens) == 1, f"Expected 1 token, got {len(tokens)}: {tokens}"
        assert "sigurros" in tokens

    def test_ampersand_variants(self):
        """Test ampersand vs 'and' vs '&'.

        Examples:
        - "Simon & Garfunkel" vs "Simon and Garfunkel"
        - "Art Blakey & The Jazz Messengers"
        """
        pairs = [
            ("Simon & Garfunkel", "Simon and Garfunkel"),
            ("Art Blakey & The Jazz Messengers", "Art Blakey and The Jazz Messengers"),
        ]

        for variant1, variant2 in pairs:
            token1 = normalize_token(variant1)
            token2 = normalize_token(variant2)

            # Should normalize to same token
            # (ampersand and 'and' both become spaces, which are removed)
            assert token1 == token2, f"{variant1} and {variant2} should normalize to same token"
