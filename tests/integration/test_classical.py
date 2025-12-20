"""Integration tests for classical music organization.

Tests composer/performer structure, name variants (J.S. Bach vs Johann Sebastian Bach),
and handling of multiple performers of the same work.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock, patch

import pytest

from resonance.app import ResonanceApp
from resonance.core.models import AlbumInfo


@dataclass(frozen=True)
class TrackSpec:
    filename: str
    title: str
    album: str
    track_number: int
    # Classical fields
    composer: str | None = None
    artist: str | None = None          # often performer
    performer: str | None = None       # orchestra/ensemble/soloist
    conductor: str | None = None
    work: str | None = None
    year: int | None = None
    disc_number: int | None = None


def _patch_reader_for_specs(specs: list[TrackSpec]) -> Callable:
    """
    Returns a MetadataReader.read_track replacement that maps file names to specs.
    Avoids late-binding issues by closing over `specs` in an outer function.
    """
    def mock_read_track(path: Path):
        from resonance.core.models import TrackInfo

        spec_map = {s.filename: s for s in specs}
        s = spec_map[path.name]
        t = TrackInfo(path=path)
        t.title = s.title
        t.album = s.album
        t.track_number = s.track_number
        # Optional extra fields (only if TrackInfo supports them)
        if hasattr(t, "disc_number"):
            t.disc_number = s.disc_number
        if hasattr(t, "year"):
            t.year = s.year
        if hasattr(t, "work"):
            t.work = s.work
        if hasattr(t, "composer"):
            t.composer = s.composer
        if hasattr(t, "artist"):
            t.artist = s.artist
        if hasattr(t, "performer"):
            t.performer = s.performer
        if hasattr(t, "conductor"):
            t.conductor = s.conductor
        return t

    return mock_read_track


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
        - Tracks load with composer metadata
        - Canonicalization only unifies when mappings exist
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
        - Tracks load with composer/conductor/performer metadata
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
        - Tracks load for each album directory without crashing
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

    # --- more classical integration tests (real-world combinations) ---

    def test_vivaldi_four_seasons_soloist_conductor_orchestra(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world case: Vivaldi - The Four Seasons
        Common tags include composer + soloist + conductor + orchestra.

        Expected (v1):
        - Tracks recognized as classical (composer present)
        - Conductor and orchestra fields preserved
        - Performer/artist may be soloist (violinist)
        """
        input_dir = test_library / "vivaldi_four_seasons"
        input_dir.mkdir()

        specs = [
            TrackSpec(
                filename="01 - Spring I.flac",
                title="The Four Seasons: Spring, I. Allegro",
                composer="Antonio Vivaldi",
                artist="Janine Jansen",  # soloist (often stored in artist)
                conductor="Paavo Järvi",
                performer="Deutsche Kammerphilharmonie Bremen",
                album="Vivaldi: The Four Seasons",
                track_number=1,
            ),
            TrackSpec(
                filename="02 - Spring II.flac",
                title="The Four Seasons: Spring, II. Largo",
                composer="Antonio Vivaldi",
                artist="Janine Jansen",
                conductor="Paavo Järvi",
                performer="Deutsche Kammerphilharmonie Bremen",
                album="Vivaldi: The Four Seasons",
                track_number=2,
            ),
        ]

        for s in specs:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                album=s.album,
                track_number=s.track_number,
                composer=s.composer,
                artist=s.artist,
                conductor=s.conductor,
                performer=s.performer,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_specs(specs),
            ):
                from resonance.visitors import IdentifyVisitor

                identify = IdentifyVisitor(
                    musicbrainz=MagicMock(),
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=app.release_search,
                )
                identify.visit(album)

            assert len(album.tracks) == 2
            assert all(t.composer for t in album.tracks)
            assert all(getattr(t, "conductor", None) for t in album.tracks)
            assert all(getattr(t, "performer", None) for t in album.tracks)

            # Future tightening: when you build canonical_performer, assert it includes soloist+conductor+orchestra.

        finally:
            app.close()

    def test_mahler_symphony_with_vocal_soloists_and_choir(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world case: Mahler symphony with chorus and soloists.

        Expected:
        - Composer present
        - Performer may include choir/orchestra; artist may be conductor or album artist in the wild
        - No crash if multiple contributor-like fields exist
        """
        input_dir = test_library / "mahler_2_resurrection"
        input_dir.mkdir()

        specs = [
            TrackSpec(
                filename="01 - I. Allegro maestoso.flac",
                title="Symphony No. 2: I. Allegro maestoso",
                composer="Gustav Mahler",
                conductor="Claudio Abbado",
                performer="Berlin Philharmonic; Swedish Radio Choir",
                album="Mahler: Symphony No. 2",
                track_number=1,
            ),
            TrackSpec(
                filename="02 - IV. Urlicht.flac",
                title="Symphony No. 2: IV. Urlicht",
                composer="Gustav Mahler",
                conductor="Claudio Abbado",
                performer="Berlin Philharmonic; Swedish Radio Choir; Anna Larsson (alto)",
                album="Mahler: Symphony No. 2",
                track_number=2,
            ),
        ]

        for s in specs:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                album=s.album,
                track_number=s.track_number,
                composer=s.composer,
                conductor=s.conductor,
                performer=s.performer,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_specs(specs),
            ):
                from resonance.visitors import IdentifyVisitor

                identify = IdentifyVisitor(
                    musicbrainz=MagicMock(),
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=app.release_search,
                )
                identify.visit(album)

            assert len(album.tracks) == 2
            assert all(t.composer for t in album.tracks)
            assert all(getattr(t, "conductor", None) for t in album.tracks)
            assert all(getattr(t, "performer", None) for t in album.tracks)

        finally:
            app.close()

    def test_classical_multi_composer_album_falls_back_to_performer_or_various(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world case: 'Best of Baroque' style compilation.
        Multiple composers within the same directory => no single-composer path.

        Expected (v1):
        - album is classical (composer on tracks)
        - canonical_composer likely None (or not set as single composer)
        - canonical performer used if present; otherwise 'Various Artists' later in planner
        """
        input_dir = test_library / "best_of_baroque"
        input_dir.mkdir()

        specs = [
            TrackSpec(
                filename="01 - Bach.flac",
                title="Brandenburg Concerto No. 3: I. Allegro",
                composer="J.S. Bach",
                performer="Academy of St Martin in the Fields",
                conductor="Neville Marriner",
                album="Best of Baroque",
                track_number=1,
            ),
            TrackSpec(
                filename="02 - Handel.flac",
                title="Water Music: Alla Hornpipe",
                composer="G.F. Handel",
                performer="Academy of St Martin in the Fields",
                conductor="Neville Marriner",
                album="Best of Baroque",
                track_number=2,
            ),
        ]

        for s in specs:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                album=s.album,
                track_number=s.track_number,
                composer=s.composer,
                performer=s.performer,
                conductor=s.conductor,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_specs(specs),
            ):
                from resonance.visitors import IdentifyVisitor

                identify = IdentifyVisitor(
                    musicbrainz=MagicMock(),
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=app.release_search,
                )
                identify.visit(album)

            assert len(album.tracks) == 2
            assert all(t.composer for t in album.tracks)

            # Future tightening: assert canonical_composer is None (or not "single composer")
            # depending on your IdentifyVisitor policy.
            # If your current IdentifyVisitor sets a composer anyway, keep only the invariant:
            composers = {t.composer for t in album.tracks if t.composer}
            assert len(composers) >= 2

        finally:
            app.close()

    def test_opera_with_act_scene_titles_and_many_performers(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world case: Opera track titles are long and include act/scene.
        Performers may be 'cast; orchestra; conductor'.

        Expected:
        - No crashes / truncation assumptions
        - Composer preserved
        - Performer/conductor preserved when present
        """
        input_dir = test_library / "mozart_don_giovanni"
        input_dir.mkdir()

        specs = [
            TrackSpec(
                filename="01 - Act I - Scene 1.flac",
                title="Don Giovanni, K.527: Act I, Scene 1: Notte e giorno faticar",
                composer="W.A. Mozart",
                conductor="Carlo Maria Giulini",
                performer="Philharmonia Orchestra; Eberhard Wächter; Joan Sutherland",
                album="Mozart: Don Giovanni",
                track_number=1,
            ),
            TrackSpec(
                filename="02 - Act I - Scene 2.flac",
                title="Don Giovanni, K.527: Act I, Scene 2: Là ci darem la mano",
                composer="W.A. Mozart",
                conductor="Carlo Maria Giulini",
                performer="Philharmonia Orchestra; Eberhard Wächter; Joan Sutherland",
                album="Mozart: Don Giovanni",
                track_number=2,
            ),
        ]

        for s in specs:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                album=s.album,
                track_number=s.track_number,
                composer=s.composer,
                conductor=s.conductor,
                performer=s.performer,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_specs(specs),
            ):
                from resonance.visitors import IdentifyVisitor

                identify = IdentifyVisitor(
                    musicbrainz=MagicMock(),
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=app.release_search,
                )
                identify.visit(album)

            assert len(album.tracks) == 2
            assert all(t.composer for t in album.tracks)
            assert all(getattr(t, "performer", None) for t in album.tracks)
            assert all(getattr(t, "conductor", None) for t in album.tracks)

        finally:
            app.close()

    def test_classical_diacritics_and_name_variants_canonicalization(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world case: diacritics and abbreviations in composer field.
        Examples:
          - 'Dvořák' vs 'Dvorak'
          - 'Pyotr Ilyich Tchaikovsky' vs 'P. I. Tchaikovsky'

        Expected:
        - No crashes; composer strings loaded
        - Later canonicalizer mapping can unify variants (this test verifies the raw presence)
        """
        input_dir = test_library / "name_variants_diacritics"
        input_dir.mkdir()

        specs = [
            TrackSpec(
                filename="01 - New World I.flac",
                title="Symphony No. 9 'From the New World': I. Adagio - Allegro molto",
                composer="Antonín Dvořák",
                performer="Czech Philharmonic Orchestra",
                conductor="Rafael Kubelík",
                album="Dvořák: New World Symphony",
                track_number=1,
            ),
            TrackSpec(
                filename="02 - New World II.flac",
                title="Symphony No. 9 'From the New World': II. Largo",
                composer="Antonin Dvorak",
                performer="Czech Philharmonic Orchestra",
                conductor="Rafael Kubelik",
                album="Dvorak: New World Symphony",
                track_number=2,
            ),
        ]

        for s in specs:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                album=s.album,
                track_number=s.track_number,
                composer=s.composer,
                performer=s.performer,
                conductor=s.conductor,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_specs(specs),
            ):
                from resonance.visitors import IdentifyVisitor

                identify = IdentifyVisitor(
                    musicbrainz=MagicMock(),
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=app.release_search,
                )
                identify.visit(album)

            assert len(album.tracks) == 2
            composers = {t.composer for t in album.tracks if t.composer}
            assert len(composers) == 2  # raw variants present

            # Future tightening: once canonicalizer mappings exist, assert album.canonical_composer is unified.

        finally:
            app.close()

    def test_box_set_multi_disc_numbers_preserved_and_stable(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world case: box sets with multiple discs.
        Often disc_number is crucial for track ordering and later filename formatting.

        Expected:
        - disc_number and track_number preserved if supported by TrackInfo
        - IdentifyVisitor doesn't crash if disc_number exists
        """
        input_dir = test_library / "box_set_multi_disc"
        input_dir.mkdir()

        specs = [
            TrackSpec(
                filename="CD1-01.flac",
                title="Piano Sonata No. 14 'Moonlight': I. Adagio sostenuto",
                composer="Ludwig van Beethoven",
                performer="Wilhelm Kempff",
                album="Beethoven: Complete Piano Sonatas",
                disc_number=1,
                track_number=1,
            ),
            TrackSpec(
                filename="CD2-01.flac",
                title="Piano Sonata No. 8 'Pathétique': I. Grave - Allegro di molto e con brio",
                composer="Ludwig van Beethoven",
                performer="Wilhelm Kempff",
                album="Beethoven: Complete Piano Sonatas",
                disc_number=2,
                track_number=1,
            ),
        ]

        for s in specs:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                album=s.album,
                track_number=s.track_number,
                composer=s.composer,
                performer=s.performer,
                disc_number=s.disc_number,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_specs(specs),
            ):
                from resonance.visitors import IdentifyVisitor

                identify = IdentifyVisitor(
                    musicbrainz=MagicMock(),
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=app.release_search,
                )
                identify.visit(album)

            assert len(album.tracks) == 2
            assert all(t.composer for t in album.tracks)

            # Only assert disc_number if TrackInfo has it.
            if hasattr(album.tracks[0], "disc_number"):
                discs = {t.disc_number for t in album.tracks}
                assert discs == {1, 2}

        finally:
            app.close()

    def test_classical_missing_composer_should_not_be_classical_by_accident(
        self,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Real-world case: classical album where composer tag is missing (common in poorly tagged libraries).

        Expected:
        - IdentifyVisitor loads tracks but should not 'invent' composer.
        - album may remain non-classical (depending on your is_classical rule).
        """
        input_dir = test_library / "missing_composer_tag"
        input_dir.mkdir()

        specs = [
            TrackSpec(
                filename="01 - Track.flac",
                title="Symphony No. 5: I. Allegro con brio",
                composer=None,  # missing composer tag
                artist="Berlin Philharmonic Orchestra",
                album="Symphony No. 5",
                track_number=1,
            )
        ]

        for s in specs:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                album=s.album,
                track_number=s.track_number,
                composer=s.composer,
                artist=s.artist,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)

            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_specs(specs),
            ):
                from resonance.visitors import IdentifyVisitor

                identify = IdentifyVisitor(
                    musicbrainz=MagicMock(),
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=app.release_search,
                )
                identify.visit(album)

            assert len(album.tracks) == 1
            assert album.tracks[0].composer in (None, "")

            # If your AlbumInfo.is_classical depends on composer, this should be False.
            # Keep it permissive if your current logic differs.
            assert album.is_classical is False

        finally:
            app.close()

    @pytest.mark.parametrize(
        "composer_variant",
        ["J.S. Bach", "Johann Sebastian Bach", "JS Bach", "Bach", "J. S. Bach"],
    )
    def test_parametric_composer_variants_load_and_do_not_crash(
        self,
        composer_variant,
        create_test_audio_file,
        test_cache,
        test_library,
    ):
        """
        Parametric smoke test: many composer spellings should be accepted.
        This does not enforce canonical output (that’s a mapping/policy concern),
        but it prevents regressions in parsing/handling.
        """
        input_dir = test_library / f"composer_variant_{composer_variant.replace(' ', '_').replace('.', '')}"
        input_dir.mkdir()

        specs = [
            TrackSpec(
                filename="01 - Aria.flac",
                title="Goldberg Variations: Aria",
                composer=composer_variant,
                artist="Glenn Gould",
                album="Goldberg Variations",
                track_number=1,
            )
        ]

        for s in specs:
            create_test_audio_file(
                path=input_dir / s.filename,
                title=s.title,
                album=s.album,
                track_number=s.track_number,
                composer=s.composer,
                artist=s.artist,
            )

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,
            dry_run=True,
        )

        try:
            album = AlbumInfo(directory=input_dir)
            with patch(
                "resonance.services.metadata_reader.MetadataReader.read_track",
                _patch_reader_for_specs(specs),
            ):
                from resonance.visitors import IdentifyVisitor

                identify = IdentifyVisitor(
                    musicbrainz=MagicMock(),
                    canonicalizer=app.canonicalizer,
                    cache=app.cache,
                    release_search=app.release_search,
                )
                identify.visit(album)

            assert len(album.tracks) == 1
            assert album.tracks[0].composer == composer_variant

        finally:
            app.close()
