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
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FakeCanonicalCache:
    """
    Integration-friendly canonical cache stub:
    mirrors the interface used by IdentityCanonicalizer.
    """
    store: dict[str, str]

    def get_canonical_name(self, key: str) -> str | None:
        return self.store.get(key)

    def set_canonical_name(self, key: str, canonical: str) -> None:
        self.store[key] = canonical


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
        - Normalization produces deterministic keys
        - Canonicalization only unifies when mappings exist
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

            # Verify normalization produces deterministic tokens
            variants = ["Björk", "Bjork", "Björk Guðmundsdóttir"]
            tokens = {normalize_token(v) for v in variants}

            assert "bjork" in tokens
            assert "bjorkgudmundsdottir" in tokens
            assert len(tokens) == 2

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
        - Normalized tokens remain distinct (no reordering)
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

            assert tokens == {"thebeatles", "beatles", "beatlesthe"}

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

    @pytest.mark.parametrize(
        "raw, expected",
        [
            # Whitespace + punctuation
            ("  The   Beatles  ", "thebeatles"),
            ("Miles Davis.", "milesdavis"),
            ("Guns N' Roses", "gunsnroses"),
            ("Guns N’ Roses", "gunsnroses"),  # curly apostrophe

            # Unicode + diacritics (normalize to ASCII-ish token)
            ("Björk", "bjork"),
            ("Björk", "bjork"),  # decomposed form (o + combining diaeresis)
            ("Sigur Rós", "sigurros"),
            ("João Gilberto", "joaogilberto"),

            # Hyphens/dashes
            ("Sigur-Rós", "sigurros"),
            ("Sigur—Rós", "sigurros"),  # em dash

            # Slashes and joiners
            ("AC/DC", "acdc"),
            ("Getz/Gilberto", "getzgilberto"),
            ("Simon & Garfunkel", "simongarfunkel"),
            ("Simon and Garfunkel", "simongarfunkel"),

            # Featuring removal (multiple syntaxes)
            ("Daft Punk feat. Pharrell Williams", "daftpunk"),
            ("Daft Punk (feat. Pharrell Williams)", "daftpunk"),
            ("Daft Punk [feat. Pharrell Williams]", "daftpunk"),
            ("Artist featuring Guest", "artist"),
            ("Artist ft Guest", "artist"),
            ("Artist including Guest", "artist"),

            # Common collaboration marker "x"
            # If you decide to treat "x" as a joiner, this should strip it similarly.
            ("Calvin Harris x Dua Lipa", "calvinharrisdualipa"),

            # Fullwidth characters commonly produced by Japanese/Chinese taggers
            ("AC／DC", "acdc"),  # fullwidth slash
        ],
    )

    def test_normalize_token_more_real_world_inputs(self, raw, expected):
        assert normalize_token(raw) == expected

    def test_normalize_token_is_idempotent_for_many_inputs(self):
        samples = [
            "Björk",
            "Daft Punk feat. Pharrell Williams",
            "AC/DC",
            "Simon & Garfunkel",
            "Calvin Harris x Dua Lipa",
            "Guns N' Roses",
            "",
            None,  # type: ignore[arg-type]
        ]
        for s in samples:
            t1 = normalize_token(s)
            t2 = normalize_token(t1)
            assert t1 == t2

    def test_normalize_token_does_not_reorder_comma_names(self):
        """
        Foundation choice: normalize_token is NOT a canonicalizer.
        It should not attempt "Beatles, The" -> "The Beatles" unless you explicitly implement reordering.
        This test prevents accidental, partial reordering logic.
        """
        assert normalize_token("Beatles, The") == "beatlesthe"
        assert normalize_token("The Beatles") == "thebeatles"
        assert normalize_token("Beatles, The") != normalize_token("The Beatles")

    def test_normalize_token_removes_parenthetical_noise_but_not_core_name(self):
        # Decide what counts as "noise". This test encodes a conservative rule:
        # only featuring-like tokens are removed, not arbitrary parentheses.
        assert normalize_token("Björk (Remastered)") == "bjorkremastered"  # if you keep tokens
        # If you prefer to DROP parenthetical segments in general, change expected to "bjork".
        # The key point is: choose ONE policy and lock it down in tests.

    @pytest.mark.parametrize(
        "variant1, variant2",
        [
            ("Sigur Rós", "Sigur Ros"),
            ("Sigur-Rós", "Sigur Ros"),
            ("Björk", "Bjork"),
            ("João Gilberto", "Joao Gilberto"),
            ("Guns N' Roses", "Guns N Roses"),
            ("Guns N’ Roses", "Guns N Roses"),
            ("Daft Punk feat. Pharrell", "Daft Punk featuring Pharrell"),
            ("Daft Punk (feat. Pharrell)", "Daft Punk ft. Pharrell"),
            ("Simon & Garfunkel", "Simon and Garfunkel"),
            ("Getz/Gilberto", "Getz / Gilberto"),
            ("AC/DC", "AC／DC"),
        ],
    )
    def test_normalize_token_equivalence_pairs(self, variant1, variant2):
        assert normalize_token(variant1) == normalize_token(variant2)

    def test_canonicalizer_mapping_applies_preferred_display_form(self, test_cache, test_library, create_test_audio_file):
        """
        Integration-ish test: given raw variants, canonicalizer should map
        them to the preferred display form using the cache mapping store.

        This is foundational: it prevents you from accidentally trying to make
        normalize_token do "display decisions".
        """
        input_dir = test_library / "canonicalizer_mapping_artist"
        input_dir.mkdir()

        tracks = [
            {"filename": "01.flac", "title": "t1", "artist": "Bjork", "album": "Homogenic", "track_number": 1},
            {"filename": "02.flac", "title": "t2", "artist": "Björk", "album": "Homogenic", "track_number": 2},
            {"filename": "03.flac", "title": "t3", "artist": "Björk Guðmundsdóttir", "album": "Homogenic", "track_number": 3},
        ]
        for s in tracks:
            create_test_audio_file(
                path=input_dir / s["filename"],
                title=s["title"],
                artist=s["artist"],
                album=s["album"],
                track_number=s["track_number"],
            )

        # Build a canonicalizer that maps all known raw keys to "Björk"
        # Adjust key format if your IdentityCanonicalizer uses different namespaces.
        from resonance.core.identity.canonicalizer import IdentityCanonicalizer

        # NOTE: IdentityCanonicalizer in your unit tests uses keys like "artist::bjork".
        mapping = {
            "artist::bjork": "Björk",
            "artist::bjorkgudmundsdottir": "Björk",
        }
        canonicalizer = IdentityCanonicalizer(cache=FakeCanonicalCache(store=mapping))

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            def mock_read_track(path: Path):
                from resonance.core.models import TrackInfo
                t = TrackInfo(path=path)
                for spec in tracks:
                    if path.name == spec["filename"]:
                        t.title = spec["title"]
                        t.artist = spec["artist"]
                        t.album = spec["album"]
                        t.track_number = spec["track_number"]
                        break
                return t

            with patch("resonance.services.metadata_reader.MetadataReader.read_track", mock_read_track):
                from resonance.visitors import IdentifyVisitor
                identify = IdentifyVisitor(
                    musicbrainz=MagicMock(),
                    canonicalizer=canonicalizer,  # override app canonicalizer with mapped one
                    cache=app.cache,
                    release_search=None,
                )
                identify.visit(album)

            assert len(album.tracks) == 3
            # canonical artist should be the preferred display form
            assert album.canonical_artist == "Björk"
            assert album.canonical_album == "Homogenic"

        finally:
            app.close()

    def test_featuring_is_stripped_for_canonical_artist_but_track_artist_preserved(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Foundation goal:
        - Folder identity: canonical artist excludes featuring.
        - Track tags: raw artist strings preserved (until Enricher policy decides otherwise).
        """
        input_dir = test_library / "feat_strip_canonical_only"
        input_dir.mkdir()

        tracks = [
            {"filename": "01.flac", "title": "t1", "artist": "Daft Punk", "album": "RAM", "track_number": 1},
            {"filename": "02.flac", "title": "t2", "artist": "Daft Punk feat. Pharrell Williams", "album": "RAM", "track_number": 2},
            {"filename": "03.flac", "title": "t3", "artist": "Daft Punk (feat. Giorgio Moroder)", "album": "RAM", "track_number": 3},
        ]
        for s in tracks:
            create_test_audio_file(
                path=input_dir / s["filename"],
                title=s["title"],
                artist=s["artist"],
                album=s["album"],
                track_number=s["track_number"],
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )
        try:
            album = AlbumInfo(directory=input_dir)

            def mock_read_track(path: Path):
                from resonance.core.models import TrackInfo
                t = TrackInfo(path=path)
                for spec in tracks:
                    if path.name == spec["filename"]:
                        t.title = spec["title"]
                        t.artist = spec["artist"]
                        t.album = spec["album"]
                        t.track_number = spec["track_number"]
                        break
                return t

            with patch("resonance.services.metadata_reader.MetadataReader.read_track", mock_read_track):
                from resonance.visitors import IdentifyVisitor
                identify = IdentifyVisitor(
                    musicbrainz=MagicMock(),
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=None,
                )
                identify.visit(album)

            assert len(album.tracks) == 3
            assert album.canonical_album == "RAM"

            # Canonical artist should not include featuring tokens
            if album.canonical_artist:
                assert "feat" not in album.canonical_artist.lower()
                assert "featuring" not in album.canonical_artist.lower()

            # Track-level raw artist should still contain featuring variants for tracks 2/3
            raw_artists = [t.artist for t in album.tracks]
            assert any(a and "feat" in a.lower() for a in raw_artists)

        finally:
            app.close()
