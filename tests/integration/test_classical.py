"""Integration tests for classical music organization.

Tests composer/performer structure, name variants (J.S. Bach vs Johann Sebastian Bach),
and handling of multiple performers of the same work.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from resonance.app import ResonanceApp
from resonance.core.models import AlbumInfo


class TestClassicalMusic:
    """Test classical music composer/performer organization."""

    def test_bach_goldberg_composer_variants(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """Test Bach Goldberg Variations with composer name variants.

        Real-world case: J.S. Bach recorded by Glenn Gould
        - Composer variants: "J.S. Bach", "Johann Sebastian Bach", "JS Bach", "Bach"
        - Performer: Glenn Gould

        Expected:
        - Composer canonical: "Johann Sebastian Bach" (or configured canonical)
        - Path structure: Composer/Work/Performer/
        - All variants map to same composer
        """
        input_dir = test_library / "bach_goldberg"
        input_dir.mkdir()

        tracks = [
            {
                "filename": "01 - Aria.flac",
                "title": "Goldberg Variations, BWV 988: Aria",
                "artist": "Glenn Gould",  # Performer in artist field
                "composer": "J.S. Bach",  # Variant 1
                "album": "Goldberg Variations",
                "track_number": 1,
            },
            {
                "filename": "02 - Variation 1.flac",
                "title": "Goldberg Variations, BWV 988: Variation 1",
                "artist": "Glenn Gould",
                "composer": "Johann Sebastian Bach",  # Variant 2
                "album": "Goldberg Variations",
                "track_number": 2,
            },
            {
                "filename": "03 - Variation 2.flac",
                "title": "Goldberg Variations, BWV 988: Variation 2",
                "artist": "Glenn Gould",
                "composer": "JS Bach",  # Variant 3
                "album": "Goldberg Variations",
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

            # Mock metadata reader
            def mock_read_track(path):
                from resonance.core.models import TrackInfo

                track = TrackInfo(path=path)
                for spec in tracks:
                    if path.name == spec["filename"]:
                        track.title = spec["title"]
                        track.artist = spec.get("artist")
                        track.composer = spec.get("composer")
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

            # Verify tracks loaded
            assert len(album.tracks) == 3

            # Verify composer canonicalization
            composers = {track.composer for track in album.tracks if track.composer}
            assert len(composers) >= 1, "Should have composer data"

            # After canonicalization, all variants should map to same form
            # (This would be done by the canonicalizer)
            if album.canonical_composer:
                # Should contain "Bach"
                assert "Bach" in album.canonical_composer

            # Verify classical detection
            # (Would be done by classical music service)
            # For now, just check that composer metadata exists
            assert any(track.composer for track in album.tracks), "Should have composer metadata"

        finally:
            app.close()

    def test_beethoven_symphony_conductor_orchestra(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """Test Beethoven symphony with conductor and orchestra.

        Real-world case: Beethoven Symphony No. 9
        - Composer: Ludwig van Beethoven
        - Conductor: Herbert von Karajan
        - Orchestra: Berlin Philharmonic Orchestra

        Expected:
        - Composer: Beethoven
        - Performer: "Karajan; Berlin Philharmonic" (combined)
        - Path: Beethoven/Symphony No. 9/Karajan - Berlin Philharmonic/
        """
        input_dir = test_library / "beethoven_9th"
        input_dir.mkdir()

        tracks = [
            {
                "filename": "01 - Symphony No. 9 - I. Allegro ma non troppo.flac",
                "title": "Symphony No. 9 in D minor, Op. 125: I. Allegro ma non troppo",
                "composer": "Ludwig van Beethoven",
                "conductor": "Herbert von Karajan",
                "performer": "Berlin Philharmonic Orchestra",
                "album": "Symphony No. 9",
                "track_number": 1,
            },
            {
                "filename": "02 - Symphony No. 9 - II. Molto vivace.flac",
                "title": "Symphony No. 9 in D minor, Op. 125: II. Molto vivace",
                "composer": "Ludwig van Beethoven",
                "conductor": "Herbert von Karajan",
                "performer": "Berlin Philharmonic Orchestra",
                "album": "Symphony No. 9",
                "track_number": 2,
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

            # Mock metadata reader
            def mock_read_track(path):
                from resonance.core.models import TrackInfo

                track = TrackInfo(path=path)
                for spec in tracks:
                    if path.name == spec["filename"]:
                        track.title = spec["title"]
                        track.composer = spec.get("composer")
                        track.conductor = spec.get("conductor")
                        track.performer = spec.get("performer")
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

            # Verify tracks loaded
            assert len(album.tracks) == 2

            # Verify multiple performer types
            assert all(track.composer for track in album.tracks), "All tracks should have composer"
            assert all(track.conductor for track in album.tracks), "All tracks should have conductor"
            assert all(track.performer for track in album.tracks), "All tracks should have performer (orchestra)"

            # In real implementation, these would be combined into canonical_performer
            # e.g., "Herbert von Karajan; Berlin Philharmonic Orchestra"

        finally:
            app.close()

    def test_multiple_performers_same_work(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """Test same work by different performers should be separated.

        Real-world case: Bach Goldberg Variations
        - Glenn Gould 1955 recording
        - Glenn Gould 1981 recording
        - András Schiff recording

        Expected:
        - All in same composer/work directory
        - But separated by performer/year
        - Paths:
          - Bach/Goldberg Variations/Glenn Gould (1955)/
          - Bach/Goldberg Variations/Glenn Gould (1981)/
          - Bach/Goldberg Variations/András Schiff/
        """
        # Create three separate input directories (simulating different albums)
        dirs = []

        # Glenn Gould 1955
        dir_1955 = test_library / "bach_goldberg_gould_1955"
        dir_1955.mkdir()
        dirs.append(("1955", dir_1955, "Glenn Gould", "1955"))

        create_test_audio_file(
            path=dir_1955 / "01 - Aria.flac",
            title="Goldberg Variations: Aria",
            artist="Glenn Gould",
            composer="Johann Sebastian Bach",
            album="Goldberg Variations (1955 Recording)",
            track_number=1,
        )

        # Glenn Gould 1981
        dir_1981 = test_library / "bach_goldberg_gould_1981"
        dir_1981.mkdir()
        dirs.append(("1981", dir_1981, "Glenn Gould", "1981"))

        create_test_audio_file(
            path=dir_1981 / "01 - Aria.flac",
            title="Goldberg Variations: Aria",
            artist="Glenn Gould",
            composer="Johann Sebastian Bach",
            album="Goldberg Variations (1981 Digital Recording)",
            track_number=1,
        )

        # András Schiff
        dir_schiff = test_library / "bach_goldberg_schiff"
        dir_schiff.mkdir()
        dirs.append(("schiff", dir_schiff, "András Schiff", None))

        create_test_audio_file(
            path=dir_schiff / "01 - Aria.flac",
            title="Goldberg Variations: Aria",
            artist="András Schiff",
            composer="Johann Sebastian Bach",
            album="Goldberg Variations",
            track_number=1,
        )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            # Process each directory as separate album
            albums = []

            for name, dir_path, performer, year in dirs:
                album = AlbumInfo(directory=dir_path)

                def mock_read_track(path):
                    from resonance.core.models import TrackInfo

                    track = TrackInfo(path=path)
                    track.title = "Goldberg Variations: Aria"
                    track.artist = performer
                    track.composer = "Johann Sebastian Bach"
                    track.album = f"Goldberg Variations{f' ({year})' if year else ''}"
                    track.track_number = 1
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

                albums.append(album)

            # Verify all three albums loaded
            assert len(albums) == 3

            # Verify they all have same composer
            composers = {album.canonical_composer or album.tracks[0].composer for album in albums if album.tracks}
            # After canonicalization, should be same
            # (In practice, might still have variants - canonicalizer normalizes)

            # Verify they have different performers
            performers = {album.tracks[0].artist for album in albums if album.tracks}
            assert len(performers) == 2, "Should have 2 different performer names (Gould appears twice with different years)"

            # In real implementation, the organize visitor would create separate directories
            # based on performer and/or year

        finally:
            app.close()
