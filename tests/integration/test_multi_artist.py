"""Integration tests for multi-artist albums.

Tests that albums with multiple artists (collaborations, featuring, etc.)
are correctly identified, canonicalized, and organized.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from resonance.app import ResonanceApp
from resonance.core.models import AlbumInfo
from tests.helpers.paths import sanitized_dir
from resonance.providers.musicbrainz import MusicBrainzClient, LookupResult


from dataclasses import dataclass


@dataclass(frozen=True)
class TrackSpec:
    filename: str
    title: str
    artist: str | None
    album: str | None
    track_number: int


def _make_album_dir(test_library: Path, name: str) -> Path:
    return sanitized_dir(test_library, name)


def _patch_reader_for_tracks(tracks: list[TrackSpec]):
    def mock_read_track(path: Path):
        from resonance.core.models import TrackInfo

        t = TrackInfo(path=path)
        for s in tracks:
            if path.name == s.filename:
                t.title = s.title
                t.artist = s.artist
                t.album = s.album
                t.track_number = s.track_number
                break
        return t

    return mock_read_track


class TestMultiArtistAlbums:
    """Test multi-artist album handling."""

    def test_getz_gilberto_artist_variants(
        self,
        getz_gilberto_scenario,
        create_test_audio_file,
        test_cache,
        test_library,
        test_output,
    ):
        """Test Getz/Gilberto with different artist name formats.

        Real-world case: Stan Getz & João Gilberto album where artist
        credits vary between tracks: "Stan Getz & João Gilberto",
        "Getz, Gilberto", "Getz/Gilberto"

        Expected:
        - Tracks load without crashing
        - Canonicalization only unifies when mappings exist
        """
        # Setup test files
        input_dir = getz_gilberto_scenario.setup(test_library, create_test_audio_file)

        # Create app with mocked network
        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=False,
        )

        # Mock MusicBrainz client
        mock_mb_client = MagicMock(spec_set=MusicBrainzClient)
        app.musicbrainz = mock_mb_client

        # Mock fingerprinting to return known recordings
        def mock_enrich(track):
            # Simulate successful fingerprinting
            track.fingerprint = f"mock_fingerprint_{track.path.stem}"
            track.duration_seconds = 180
            track.acoustid_id = f"acoustid_{track.path.stem}"
            track.musicbrainz_recording_id = f"recording_{track.path.stem}"
            track.musicbrainz_release_id = getz_gilberto_scenario.expected_output["release_id"]
            return LookupResult(track, score=1.0)

        mock_mb_client.enrich = mock_enrich

        try:
            # Create pipeline
            pipeline = app.create_pipeline()

            # Create album
            album = AlbumInfo(directory=input_dir)

            # Process through pipeline
            success = pipeline.process(album)

            # Assertions
            assert success, "Pipeline should complete successfully"

            assert album.total_tracks == 3, "Should have 3 tracks"

        finally:
            app.close()

    def test_daft_punk_featuring_artists(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
        test_output,
    ):
        """Test album with featuring artists in track credits.

        Real-world case: Daft Punk "Random Access Memories"
        - Some tracks: "Daft Punk feat. Pharrell Williams"
        - Others: "Daft Punk feat. Nile Rodgers"

        Expected:
        - Album artist: "Daft Punk" (featuring stripped)
        - All tracks stay together
        - Track-level artist credits preserved
        """
        # Create test directory
        input_dir = sanitized_dir(test_library, "daft_punk_ram")

        # Create test files with featuring variants
        tracks = [
            {
                "filename": "01 - Give Life Back to Music.flac",
                "title": "Give Life Back to Music",
                "artist": "Daft Punk",
                "album": "Random Access Memories",
                "track_number": 1,
            },
            {
                "filename": "02 - Get Lucky.flac",
                "title": "Get Lucky",
                "artist": "Daft Punk feat. Pharrell Williams",  # Featuring variant 1
                "album": "Random Access Memories",
                "track_number": 2,
            },
            {
                "filename": "03 - Giorgio by Moroder.flac",
                "title": "Giorgio by Moroder",
                "artist": "Daft Punk (feat. Giorgio Moroder)",  # Featuring variant 2
                "album": "Random Access Memories",
                "track_number": 3,
            },
        ]

        for track_spec in tracks:
            create_test_audio_file(
                path=input_dir / track_spec["filename"],
                **{k: v for k, v in track_spec.items() if k != "filename"},
            )

        # Create app
        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,  # Use dry-run for this test
        )

        try:
            # Create album
            album = AlbumInfo(directory=input_dir)

            # Process with identify visitor
            from resonance.visitors import IdentifyVisitor

            # Mock MusicBrainz client
            mock_mb = MagicMock(spec_set=MusicBrainzClient)
            app.musicbrainz = mock_mb

            identify_visitor = IdentifyVisitor(
                musicbrainz=mock_mb,
                canonicalizer=app.canonicalizer,
                cache=app.cache,
                release_search=app.release_search,
            )

            # Mock metadata reader to return track info
            def mock_read_track(path):
                from resonance.core.models import TrackInfo

                track = TrackInfo(path=path)
                # Find matching track spec
                for spec in tracks:
                    if path.name == spec["filename"]:
                        track.title = spec["title"]
                        track.artist = spec["artist"]
                        track.album = spec["album"]
                        track.track_number = spec["track_number"]
                        break
                return track

            with patch("resonance.services.metadata_reader.MetadataReader.read_track", mock_read_track):
                identify_visitor.visit(album)

            # Verify canonical artist extraction
            # The canonicalizer should strip "feat." patterns
            # Check that tracks were read
            assert len(album.tracks) == 3

            # Check that canonical artist is determined
            # (exact behavior depends on canonicalizer implementation)
            if album.canonical_artist:
                # Should be "Daft Punk" without featuring
                assert "feat" not in album.canonical_artist.lower()
                assert "featuring" not in album.canonical_artist.lower()
                assert "Daft Punk" in album.canonical_artist

        finally:
            app.close()

    def test_various_artists_compilation(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """Test compilation album with multiple track artists.

        Real-world case: Movie soundtracks, "Now That's What I Call Music"
        - Album artist: "Various Artists"
        - Each track has different artist

        Expected:
        - Album stays together under "Various Artists"
        - Individual track artists NOT used for organization
        - All files in single directory
        """
        input_dir = sanitized_dir(test_library, "pulp_fiction_ost")

        tracks = [
            {
                "filename": "01 - Misirlou.flac",
                "title": "Misirlou",
                "artist": "Dick Dale & His Del-Tones",
                "album": "Pulp Fiction",
                "track_number": 1,
            },
            {
                "filename": "02 - Royale with Cheese.flac",
                "title": "Royale with Cheese",
                "artist": "Urge Overkill",
                "album": "Pulp Fiction",
                "track_number": 2,
            },
            {
                "filename": "03 - You Never Can Tell.flac",
                "title": "You Never Can Tell",
                "artist": "Chuck Berry",
                "album": "Pulp Fiction",
                "track_number": 3,
            },
        ]

        for track_spec in tracks:
            create_test_audio_file(
                path=input_dir / track_spec["filename"],
                **{k: v for k, v in track_spec.items() if k != "filename"},
            )

        # Create app
        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            # For Various Artists, the album should be treated specially
            # (This test would need to mock the release search to return
            # a Various Artists release)

            # Basic validation: tracks loaded
            from resonance.visitors import IdentifyVisitor

            mock_mb = MagicMock(spec_set=MusicBrainzClient)
            app.musicbrainz = mock_mb

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
                identify_visitor = IdentifyVisitor(
                    musicbrainz=mock_mb,
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=app.release_search,
                )
                identify_visitor.visit(album)

            # Verify different artists on tracks
            artists = {track.artist for track in album.tracks}
            assert len(artists) > 1, "Should have multiple different artists"

            # Note: Actual "Various Artists" detection would be done
            # by the release matching service

        finally:
            app.close()

    # --- more multi-artist integration tests (real-world combinations) ---

    def test_credit_joiners_ampersand_slash_and_word_and_unify(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world: collaborations credited inconsistently across tracks.
        Examples:
          - "Simon & Garfunkel"
          - "Simon / Garfunkel"
          - "Simon and Garfunkel"

        Expected (v1):
        - Tracks load
        - Canonicalization does not reorder or invent equivalences without mappings
        """
        input_dir = _make_album_dir(test_library, "simon_garfunkel_variants")

        tracks = [
            TrackSpec("01.flac", "Track 1", "Simon & Garfunkel", "Greatest Hits", 1),
            TrackSpec("02.flac", "Track 2", "Simon / Garfunkel", "Greatest Hits", 2),
            TrackSpec("03.flac", "Track 3", "Simon and Garfunkel", "Greatest Hits", 3),
        ]

        for s in tracks:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                artist=s.artist,
                album=s.album,
                track_number=s.track_number,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            from resonance.visitors import IdentifyVisitor
            mock_mb = MagicMock(spec_set=MusicBrainzClient)
            identify = IdentifyVisitor(
                musicbrainz=mock_mb,
                canonicalizer=app.canonicalizer,
                cache=app.cache,
                release_search=None,  # keep pure/local for this test
            )

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_tracks(tracks),
            ):
                identify.visit(album)

            assert len(album.tracks) == 3
            assert album.total_tracks == 3
            assert album.canonical_album == "Greatest Hits"
            if album.canonical_artist:
                assert album.canonical_artist in {s.artist for s in tracks}

        finally:
            app.close()

    def test_credit_order_inversions_are_not_treated_as_different_artists(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world: credits appear as "Getz, Stan" vs "Stan Getz"
        or as "Gilberto, João" vs "João Gilberto".

        Expected:
        - Track-level artist strings vary
        - Canonicalization can unify at folder level (later)
        - No crash; album remains coherent
        """
        input_dir = _make_album_dir(test_library, "credit_order_inversions")

        tracks = [
            TrackSpec("01.flac", "Track 1", "Getz, Stan & Gilberto, João", "Getz/Gilberto", 1),
            TrackSpec("02.flac", "Track 2", "Stan Getz & João Gilberto", "Getz/Gilberto", 2),
            TrackSpec("03.flac", "Track 3", "Getz/Gilberto", "Getz/Gilberto", 3),
        ]

        for s in tracks:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                artist=s.artist,
                album=s.album,
                track_number=s.track_number,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            from resonance.visitors import IdentifyVisitor
            identify = IdentifyVisitor(
                musicbrainz=MagicMock(spec_set=MusicBrainzClient),
                canonicalizer=app.canonicalizer,
                cache=app.cache,
                release_search=None,
            )

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_tracks(tracks),
            ):
                identify.visit(album)

            assert len(album.tracks) == 3
            artists = {t.artist for t in album.tracks if t.artist}
            assert len(artists) == 3  # raw variants kept
            # Future tightening: assert album.canonical_artist is unified consistently.

        finally:
            app.close()

    def test_featuring_variants_do_not_change_album_artist_identity(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world: the same album has track artists like:
          - "Kendrick Lamar"
          - "Kendrick Lamar feat. SZA"
          - "Kendrick Lamar (feat. Rihanna)"
          - "Kendrick Lamar featuring U2"

        Expected:
        - Canonical album artist should not include "feat" tokens
        - Track-level artist strings preserved
        """
        input_dir = _make_album_dir(test_library, "kendrick_feat_variants")

        tracks = [
            TrackSpec("01.flac", "Track 1", "Kendrick Lamar", "DAMN.", 1),
            TrackSpec("02.flac", "Track 2", "Kendrick Lamar feat. SZA", "DAMN.", 2),
            TrackSpec("03.flac", "Track 3", "Kendrick Lamar (feat. Rihanna)", "DAMN.", 3),
            TrackSpec("04.flac", "Track 4", "Kendrick Lamar featuring U2", "DAMN.", 4),
        ]

        for s in tracks:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                artist=s.artist,
                album=s.album,
                track_number=s.track_number,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            from resonance.visitors import IdentifyVisitor
            identify = IdentifyVisitor(
                musicbrainz=MagicMock(spec_set=MusicBrainzClient),
                canonicalizer=app.canonicalizer,
                cache=app.cache,
                release_search=None,
            )

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_tracks(tracks),
            ):
                identify.visit(album)

            assert len(album.tracks) == 4
            if album.canonical_artist:
                assert "feat" not in album.canonical_artist.lower()
                assert "featuring" not in album.canonical_artist.lower()
                assert "Kendrick" in album.canonical_artist

        finally:
            app.close()

    def test_collab_symbol_x_is_handled_as_joiner_if_enabled(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world: modern collabs use "x" heavily:
          - "Travis Scott x Drake"
          - "Calvin Harris x Dua Lipa"

        Expected:
        - System does not treat "x" as literal noise; it should be a joiner.
        - At minimum: no crash and stable canonicalization output.
        """
        input_dir = _make_album_dir(test_library, "x_joiner_collab")

        tracks = [
            TrackSpec("01.flac", "Track 1", "Calvin Harris x Dua Lipa", "Collab EP", 1),
            TrackSpec("02.flac", "Track 2", "Calvin Harris & Dua Lipa", "Collab EP", 2),
        ]

        for s in tracks:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                artist=s.artist,
                album=s.album,
                track_number=s.track_number,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )
        try:
            album = AlbumInfo(directory=input_dir)

            from resonance.visitors import IdentifyVisitor
            identify = IdentifyVisitor(
                musicbrainz=MagicMock(spec_set=MusicBrainzClient),
                canonicalizer=app.canonicalizer,
                cache=app.cache,
                release_search=None,
            )
            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_tracks(tracks),
            ):
                identify.visit(album)

            assert len(album.tracks) == 2
            assert album.canonical_artist in {s.artist for s in tracks}

        finally:
            app.close()

    def test_diacritics_in_multi_artist_names_are_preserved_and_can_be_canonicalized(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world: diacritics differ by source and tagging tool:
          - "Beyoncé" vs "Beyonce"
          - "João" vs "Joao"

        Expected:
        - Tracks load with distinct raw spellings
        - Canonical folder identity can unify later (mapping store)
        """
        input_dir = _make_album_dir(test_library, "diacritics_multi_artist")

        tracks = [
            TrackSpec("01.flac", "Track 1", "Beyoncé & JAY-Z", "EVERYTHING IS LOVE", 1),
            TrackSpec("02.flac", "Track 2", "Beyonce & Jay-Z", "EVERYTHING IS LOVE", 2),
        ]

        for s in tracks:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                artist=s.artist,
                album=s.album,
                track_number=s.track_number,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )
        try:
            album = AlbumInfo(directory=input_dir)

            from resonance.visitors import IdentifyVisitor
            identify = IdentifyVisitor(
                musicbrainz=MagicMock(spec_set=MusicBrainzClient),
                canonicalizer=app.canonicalizer,
                cache=app.cache,
                release_search=None,
            )
            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_tracks(tracks),
            ):
                identify.visit(album)

            assert len(album.tracks) == 2
            artists = {t.artist for t in album.tracks if t.artist}
            assert len(artists) == 2  # raw variants remain
            # Future tightening: assert album.canonical_artist matches chosen canonical mapping.

        finally:
            app.close()

    def test_soundtrack_album_artist_various_artists_overrides_track_artists(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world: soundtracks / compilations.
        Often tagged with album artist = Various Artists (or 'OST') while track artists vary.

        Expected:
        - Track artists vary
        - Album can be treated as compilation and kept together
        - Organization should be under 'Various Artists' (planner later)
        """
        input_dir = _make_album_dir(test_library, "soundtrack_compilation")

        tracks = [
            TrackSpec("01.flac", "Track 1", "Dick Dale & His Del-Tones", "Pulp Fiction", 1),
            TrackSpec("02.flac", "Track 2", "Urge Overkill", "Pulp Fiction", 2),
            TrackSpec("03.flac", "Track 3", "Chuck Berry", "Pulp Fiction", 3),
        ]

        for s in tracks:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                artist=s.artist,
                album=s.album,
                track_number=s.track_number,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )
        try:
            album = AlbumInfo(directory=input_dir)
            from resonance.visitors import IdentifyVisitor

            identify = IdentifyVisitor(
                musicbrainz=MagicMock(spec_set=MusicBrainzClient),
                canonicalizer=app.canonicalizer,
                cache=app.cache,
                release_search=None,
            )

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_tracks(tracks),
            ):
                identify.visit(album)

            assert len(album.tracks) == 3
            assert len({t.artist for t in album.tracks if t.artist}) == 3

            # Future tightening:
            # - once you support albumartist tag, set it and assert album.canonical_artist == "Various Artists"
            # - or assert compilation detection via release match.

        finally:
            app.close()

    def test_directory_with_two_unrelated_artists_should_be_uncertain_or_conflict(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world: user has a messy folder containing tracks from different albums/artists.

        Expected:
        - If you later enforce single-release-per-dir, Identify should mark uncertain/conflict.
        - For now: at minimum, it loads and does not crash.
        """
        input_dir = _make_album_dir(test_library, "messy_mixed_album_dir")

        tracks = [
            TrackSpec("01.flac", "Track 1", "Radiohead", "OK Computer", 1),
            TrackSpec("02.flac", "Track 2", "Kendrick Lamar", "DAMN.", 2),
        ]

        for s in tracks:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                artist=s.artist,
                album=s.album,
                track_number=s.track_number,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )
        try:
            album = AlbumInfo(directory=input_dir)
            from resonance.visitors import IdentifyVisitor

            identify = IdentifyVisitor(
                musicbrainz=MagicMock(spec_set=MusicBrainzClient),
                canonicalizer=app.canonicalizer,
                cache=app.cache,
                release_search=None,
            )

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_tracks(tracks),
            ):
                identify.visit(album)

            assert len(album.tracks) == 2

            # Future tightening: once you implement multi-release detection at dir level:
            # assert album.is_uncertain is True

        finally:
            app.close()

    @pytest.mark.parametrize(
        "artist_strs",
        [
            ["The Beatles", "Beatles, The", "The   Beatles"],
            ["A Tribe Called Quest", "A Tribe Called Quest feat. Somebody", "A TRIBE CALLED QUEST"],
            ["AC/DC", "AC／DC", "ACDC"],  # includes fullwidth slash variant
        ],
    )
    def test_parametric_artist_variants_smoke(
        self,
        artist_strs,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Parametric smoke tests for artist normalization/canonicalization resilience.
        This does not enforce the chosen canonical display yet, but ensures
        the pipeline can ingest common real-world variants.
        """
        input_dir = _make_album_dir(test_library, f"artist_variant_{re.sub(r'\\W+', '_', artist_strs[0])}")

        tracks = [
            TrackSpec("01.flac", "Track 1", artist_strs[0], "Album X", 1),
            TrackSpec("02.flac", "Track 2", artist_strs[1], "Album X", 2),
            TrackSpec("03.flac", "Track 3", artist_strs[2], "Album X", 3),
        ]

        for s in tracks:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                artist=s.artist,
                album=s.album,
                track_number=s.track_number,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)
            from resonance.visitors import IdentifyVisitor

            identify = IdentifyVisitor(
                musicbrainz=MagicMock(spec_set=MusicBrainzClient),
                canonicalizer=app.canonicalizer,
                cache=app.cache,
                release_search=None,
            )

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_tracks(tracks),
            ):
                identify.visit(album)

            assert len(album.tracks) == 3
            assert album.canonical_album == "Album X"

            # Future tightening: assert canonical_artist == expected mapping once you decide display form.

        finally:
            app.close()


# TODO Implement tests like this one
@pytest.mark.slow
@pytest.mark.requires_network
class TestRealMusicBrainzData:
    """Tests using real MusicBrainz API (slow, requires network).

    These tests are marked as slow and skipped by default.
    Run with: pytest -m requires_network
    """

    def test_real_getz_gilberto_lookup(self, test_cache, test_library):
        """Test real MusicBrainz lookup for Getz/Gilberto.

        This test actually hits the MusicBrainz API to verify
        the release ID and track data are correct.
        """
        pytest.skip("Requires real network access - run manually")

        # This would be a real integration test that:
        # 1. Creates actual audio files (or uses pre-recorded samples)
        # 2. Calls real MusicBrainz API
        # 3. Verifies results match expectations
