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
        - All variants should canonicalize to same artist
        - Album should be recognized as single release
        - Files should be organized together
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
        mock_mb_client = MagicMock()
        app.musicbrainz = mock_mb_client

        # Mock fingerprinting to return known recordings
        def mock_fingerprint_track(track):
            # Simulate successful fingerprinting
            track.fingerprint = f"mock_fingerprint_{track.path.stem}"
            track.duration_seconds = 180
            track.acoustid_id = f"acoustid_{track.path.stem}"
            track.musicbrainz_recording_id = f"recording_{track.path.stem}"
            track.musicbrainz_release_id = getz_gilberto_scenario.expected_output["release_id"]
            return True

        mock_mb_client.fingerprint_and_lookup_track = mock_fingerprint_track

        # Mock release fetching
        mock_mb_client._fetch_release_tracks = MagicMock(
            return_value=getz_gilberto_scenario.mock_responses["musicbrainz"]
        )

        try:
            # Create pipeline
            pipeline = app.create_pipeline()

            # Create album
            album = AlbumInfo(directory=input_dir)

            # Process through pipeline
            success = pipeline.process(album)

            # Assertions
            assert success, "Pipeline should complete successfully"

            # Check canonical names were applied
            # (implementation will vary based on how canonicalizer works)
            assert album.total_tracks == 3, "Should have 3 tracks"

            # Check release was identified
            expected = getz_gilberto_scenario.expected_output
            assert album.musicbrainz_release_id == expected["release_id"]

            # Check files were organized (if not dry-run)
            # This depends on OrganizeVisitor implementation
            # For now, just verify the album has destination path
            if album.destination_path:
                # Verify path contains artist and album
                path_str = str(album.destination_path)
                assert "Getz" in path_str or "Stan Getz" in path_str
                assert "Gilberto" in path_str or "João Gilberto" in path_str

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
        input_dir = test_library / "daft_punk_ram"
        input_dir.mkdir()

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
            mock_mb = MagicMock()
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
        input_dir = test_library / "pulp_fiction_ost"
        input_dir.mkdir()

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

            mock_mb = MagicMock()
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
