"""Integration tests for AcoustID fingerprint-based identification end-to-end."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from resonance.core.identifier import DirectoryEvidence, TrackEvidence, identify
from resonance.providers.acoustid import AcoustIDClient


class TestAcoustIDIntegration:
    """Test AcoustID integration with mocked API responses."""

    def test_fingerprint_path_end_to_end(self, tmp_path: Path) -> None:
        """Test complete fingerprint identification flow with mocked AcoustID."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        # Create test audio files with fingerprints
        tracks = []
        for i in range(2):
            audio_file = tmp_path / f"track{i+1}.flac"
            audio_file.write_text("fake audio")

            # Create metadata with fingerprint
            meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
            meta_file.write_text(f'''{{
                "duration_seconds": 180,
                "fingerprint": "fp-{i+1}"
            }}''')
            tracks.append(audio_file)

        # Create evidence
        from resonance.core.identifier import extract_evidence
        evidence = extract_evidence(tracks, fingerprint_reader=lambda p: f"fp-{tracks.index(p)+1}")

        # Verify evidence has fingerprints
        assert evidence.has_fingerprints
        assert len([t for t in evidence.tracks if t.fingerprint_id]) == 2

        # Create AcoustID client (only supports fingerprints, not metadata)
        client = AcoustIDClient()

        # Mock AcoustID API response with release candidates
        mock_releases = [
            {
                "provider": "acoustid",
                "release_id": "mb-123",
                "title": "Test Album",
                "artist": "Test Artist",
                "tracks": [
                    {
                        "position": 1,
                        "title": "Track 1",
                        "duration_seconds": 180,
                        "fingerprint_id": "fp-1",
                    },
                    {
                        "position": 2,
                        "title": "Track 2",
                        "duration_seconds": 180,
                        "fingerprint_id": "fp-2",
                    }
                ]
            }
        ]

        # Convert to ProviderRelease objects
        from resonance.core.identifier import ProviderRelease, ProviderTrack
        provider_releases = []
        for release_data in mock_releases:
            tracks_data = release_data["tracks"]
            provider_tracks = []
            for track_data in tracks_data:
                provider_tracks.append(ProviderTrack(
                    position=track_data["position"],
                    title=track_data["title"],
                    duration_seconds=track_data.get("duration_seconds"),
                    fingerprint_id=track_data.get("fingerprint_id"),
                ))

            provider_releases.append(ProviderRelease(
                provider=release_data["provider"],
                release_id=release_data["release_id"],
                title=release_data["title"],
                artist=release_data["artist"],
                tracks=tuple(provider_tracks),
            ))

        # Mock the pyacoustid.lookup function to avoid real API calls
        mock_acoustid_results = [
            {
                "score": 0.9,
                "recordings": [
                    {
                        "id": "recording-123",
                        "title": "Test Album",
                        "artists": [{"name": "Test Artist"}],
                    }
                ]
            }
        ]

        with patch('acoustid.lookup', return_value=mock_acoustid_results) as mock_lookup:
            # Run identification - this should work since AcoustID supports fingerprints
            result = identify(evidence, client)

            # Verify lookup was called with the first fingerprint
            mock_lookup.assert_called_once()
            args, kwargs = mock_lookup.call_args
            assert args[0] == "fp-1"  # First fingerprint
            assert "lookup" in args[1]  # URL contains lookup
            assert kwargs.get("meta") == ["recordings", "releases"]  # Meta parameter

            # Verify we got results
            assert len(result.candidates) == 1
            candidate = result.candidates[0]
            assert candidate.release.title == "Test Album"
            assert candidate.release.artist == "Test Artist"
            # AcoustID returns recording info, not track-specific fingerprint matches
            assert candidate.fingerprint_coverage == 0.0  # No direct track matches

    def test_fingerprint_partial_matches(self, tmp_path: Path) -> None:
        """Test fingerprint identification with partial matches."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        # Create 3 tracks, only 2 with fingerprints
        tracks = []
        for i in range(3):
            audio_file = tmp_path / f"track{i+1}.flac"
            audio_file.write_text("fake audio")

            # Only first two tracks have fingerprints
            fingerprint = f"fp-{i+1}" if i < 2 else None
            meta_content = '{"duration_seconds": 180'
            if fingerprint:
                meta_content += f', "fingerprint": "{fingerprint}"'
            meta_content += '}'

            meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
            meta_file.write_text(meta_content)
            tracks.append(audio_file)

        # Create evidence
        from resonance.core.identifier import extract_evidence
        evidence = extract_evidence(tracks, fingerprint_reader=lambda p: f"fp-{tracks.index(p)+1}" if tracks.index(p) < 2 else None)

        # Create AcoustID client (only supports fingerprints)
        client = AcoustIDClient()

        # Mock release with only 2 tracks matching fingerprints
        from resonance.core.identifier import ProviderRelease, ProviderTrack
        mock_release = ProviderRelease(
            provider="acoustid",
            release_id="mb-456",
            title="Partial Match Album",
            artist="Test Artist",
            tracks=(
                ProviderTrack(position=1, title="Track 1", fingerprint_id="fp-1"),
                ProviderTrack(position=2, title="Track 2", fingerprint_id="fp-2"),
                ProviderTrack(position=3, title="Track 3"),  # No fingerprint match
            ),
        )

        # Mock pyacoustid to return a partial match result
        mock_acoustid_results = [
            {
                "score": 0.8,
                "recordings": [
                    {
                        "id": "recording-456",
                        "title": "Partial Match Album",
                        "artists": [{"name": "Test Artist"}],
                    }
                ]
            }
        ]

        with patch('acoustid.lookup', return_value=mock_acoustid_results) as mock_lookup:
            result = identify(evidence, client)

            # Should call lookup with first available fingerprint
            mock_lookup.assert_called_once()
            args = mock_lookup.call_args[0]
            assert args[0] == "fp-1"  # First fingerprint

            assert len(result.candidates) == 1
            candidate = result.candidates[0]
            # AcoustID returns recording info, not track-specific fingerprint matches
            assert candidate.fingerprint_coverage == 0.0  # No direct track matches
            assert candidate.track_count_match is False  # Single track vs 3 evidence tracks

    def test_fingerprint_no_matches_fallback_to_metadata(self, tmp_path: Path) -> None:
        """Test fallback to metadata search when fingerprints don't match."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        # Create tracks with fingerprints but no AcoustID matches
        tracks = []
        for i in range(2):
            audio_file = tmp_path / f"track{i+1}.flac"
            audio_file.write_text("fake audio")

            meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
            meta_file.write_text(f'''{{
                "duration_seconds": 180,
                "fingerprint": "fp-{i+1}",
                "tags": {{
                    "artist": "Fallback Artist",
                    "album": "Fallback Album"
                }}
            }}''')
            tracks.append(audio_file)

        # Create evidence
        from resonance.core.identifier import extract_evidence
        evidence = extract_evidence(tracks, fingerprint_reader=lambda p: f"fp-{tracks.index(p)+1}")

        # Create clients - AcoustID returns no matches, MusicBrainz returns match
        acoustid_client = AcoustIDClient()
        from resonance.providers.musicbrainz import MusicBrainzClient

        # Mock MusicBrainz release
        from resonance.core.identifier import ProviderRelease, ProviderTrack
        mb_release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-fallback",
            title="Fallback Album",
            artist="Fallback Artist",
            tracks=(
                ProviderTrack(position=1, title="Track 1"),
                ProviderTrack(position=2, title="Track 2"),
            ),
        )

        # Create combined client
        from resonance.core.provider_fusion import NamedProvider, CombinedProviderClient
        from resonance.core.identifier import ProviderCapabilities

        class MockMBClient:
            @property
            def capabilities(self) -> ProviderCapabilities:
                return ProviderCapabilities(supports_fingerprints=False, supports_metadata=True)

            def search_by_fingerprints(self, fingerprints):
                return []

            def search_by_metadata(self, artist, album, track_count):
                return [mb_release]

        providers = [
            NamedProvider("acoustid", acoustid_client),
            NamedProvider("musicbrainz", MockMBClient()),
        ]
        combined_client = CombinedProviderClient(tuple(providers))

        # Mock AcoustID to return no matches (empty results)
        with patch('acoustid.lookup', return_value=[]):
            result = identify(evidence, combined_client)

            # Should get result from metadata fallback
            assert len(result.candidates) >= 1
            # Verify the tier indicates fallback worked
            assert result.tier in ["CERTAIN", "PROBABLE", "UNSURE"]

    def test_fingerprint_error_handling(self, tmp_path: Path) -> None:
        """Test graceful handling of fingerprint extraction errors."""
        # Create a track that will cause fingerprint extraction to fail
        audio_file = tmp_path / "problematic.flac"
        audio_file.write_text("fake audio")

        # No metadata file - should cause extraction to fail gracefully
        tracks = [audio_file]

        # Create evidence
        from resonance.core.identifier import extract_evidence
        evidence = extract_evidence(tracks, fingerprint_reader=lambda p: None)  # Always fails

        # Should not have fingerprints
        assert not evidence.has_fingerprints

        # Identification should work (no fingerprint search since no fingerprints)
        client = AcoustIDClient()
        with patch.object(client, 'search_by_fingerprints', return_value=[]) as mock_search:
            result = identify(evidence, client)

            # Should NOT call fingerprint search when there are no fingerprints
            mock_search.assert_not_called()

            # Should result in UNSURE tier with no candidates
            assert result.tier == result.tier.UNSURE
            assert len(result.candidates) == 0

    def test_offline_fingerprint_semantics(self, tmp_path: Path) -> None:
        """Test fingerprint identification in offline mode."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        # Create tracks with fingerprints
        tracks = []
        for i in range(1):
            audio_file = tmp_path / f"track{i+1}.flac"
            audio_file.write_text("fake audio")

            meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
            meta_file.write_text(f'{{"duration_seconds": 180, "fingerprint": "fp-{i+1}"}}')
            tracks.append(audio_file)

        # Create evidence
        from resonance.core.identifier import extract_evidence
        evidence = extract_evidence(tracks, fingerprint_reader=lambda p: f"fp-{tracks.index(p)+1}")

        # Create AcoustID client
        client = AcoustIDClient()

        # Mock offline mode - simulate network/API failure
        from resonance.errors import RuntimeFailure

        # Mock acoustid.lookup to raise an exception that simulates network failure
        with patch('acoustid.lookup', side_effect=Exception("Network is unreachable")):
            # Should handle the exception gracefully and return empty results
            result = identify(evidence, client)

            # Should result in UNSURE tier with no candidates due to API failure
            assert result.tier == result.tier.UNSURE
            assert len(result.candidates) == 0

    def test_combined_provider_integration(self, tmp_path: Path) -> None:
        """Test full integration of all three providers (AcoustID + MusicBrainz + Discogs)."""
        # Create test audio files with metadata tags
        tracks = []
        for i in range(2):
            audio_file = tmp_path / f"track{i+1}.flac"
            audio_file.write_text("fake audio")

            # Create metadata with fingerprint AND tags
            meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
            meta_file.write_text(f'''{{
                "duration_seconds": 180,
                "fingerprint": "fp-{i+1}",
                "tags": {{
                    "artist": "Test Artist",
                    "album": "Test Album"
                }}
            }}''')
            tracks.append(audio_file)

        # Create evidence with both fingerprints and metadata
        from resonance.core.identifier import extract_evidence
        evidence = extract_evidence(tracks, fingerprint_reader=lambda p: f"fp-{tracks.index(p)+1}")

        # Create combined provider client with all three providers
        from resonance.core.provider_fusion import NamedProvider, CombinedProviderClient

        # Mock AcoustID provider (since pyacoustid may not be available)
        from resonance.core.identifier import ProviderCapabilities, ProviderRelease, ProviderTrack

        class MockAcoustIDClient:
            @property
            def capabilities(self) -> ProviderCapabilities:
                return ProviderCapabilities(supports_fingerprints=True, supports_metadata=False)

            def search_by_fingerprints(self, fingerprints):
                if fingerprints and fingerprints[0] == "fp-1":
                    return [ProviderRelease(
                        provider="acoustid",
                        release_id="acoustid-recording-123",
                        title="Test Album",
                        artist="Test Artist",
                        tracks=(
                            ProviderTrack(position=1, title="Track 1"),
                            ProviderTrack(position=2, title="Track 2"),
                        ),
                    )]
                return []

            def search_by_metadata(self, artist, album, track_count):
                return []

        # Mock MusicBrainz provider
        class MockMBClient:
            @property
            def capabilities(self) -> ProviderCapabilities:
                return ProviderCapabilities(supports_fingerprints=False, supports_metadata=True)

            def search_by_fingerprints(self, fingerprints):
                return []

            def search_by_metadata(self, artist, album, track_count):
                if artist == "Test Artist" and album == "Test Album":
                    return [ProviderRelease(
                        provider="musicbrainz",
                        release_id="mb-test-123",
                        title="Test Album",
                        artist="Test Artist",
                        tracks=(
                            ProviderTrack(position=1, title="Track 1"),
                            ProviderTrack(position=2, title="Track 2"),
                        ),
                    )]
                return []

        # Mock Discogs provider
        class MockDiscogsClient:
            @property
            def capabilities(self) -> ProviderCapabilities:
                return ProviderCapabilities(supports_fingerprints=False, supports_metadata=True)

            def search_by_fingerprints(self, fingerprints):
                return []

            def search_by_metadata(self, artist, album, track_count):
                if artist == "Test Artist" and album == "Test Album":
                    return [ProviderRelease(
                        provider="discogs",
                        release_id="dg-test-456",
                        title="Test Album",
                        artist="Test Artist",
                        tracks=(
                            ProviderTrack(position=1, title="Track 1"),
                            ProviderTrack(position=2, title="Track 2"),
                        ),
                    )]
                return []

        providers = [
            NamedProvider("acoustid", MockAcoustIDClient()),
            NamedProvider("musicbrainz", MockMBClient()),
            NamedProvider("discogs", MockDiscogsClient()),
        ]
        combined_client = CombinedProviderClient(tuple(providers))

        # Test 1: AcoustID finds results (fingerprint priority)
        result = identify(evidence, combined_client)

        # Should get results from multiple providers (AcoustID + MusicBrainz)
        # AcoustID should be prioritized due to fingerprint capability
        assert len(result.candidates) >= 1
        providers_found = {c.release.provider for c in result.candidates}
        assert "acoustid" in providers_found  # AcoustID found via fingerprints
        assert "musicbrainz" in providers_found  # MusicBrainz found via metadata

        # Test 2: AcoustID fails, fallback to metadata providers
        # Create evidence without fingerprints
        evidence_no_fp = extract_evidence(tracks, fingerprint_reader=lambda p: None)

        result = identify(evidence_no_fp, combined_client)

        # Should get results from MusicBrainz and Discogs
        assert len(result.candidates) >= 1
        # Results should include both MB and Discogs releases
        providers_found = {c.release.provider for c in result.candidates}
        assert "musicbrainz" in providers_found or "discogs" in providers_found

    def test_two_channel_identification_flow(self, tmp_path: Path) -> None:
        """Test complete two-channel identification: fingerprints + metadata."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        # Create evidence with strong metadata hints
        audio_file = tmp_path / "track1.flac"
        audio_file.write_text("fake audio")
        meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
        meta_file.write_text('''{
            "duration_seconds": 180,
            "fingerprint": "fp-test",
            "tags": {
                "artist": "Known Artist",
                "album": "Known Album"
            }
        }''')

        from resonance.core.identifier import extract_evidence
        evidence = extract_evidence([audio_file], fingerprint_reader=lambda p: "fp-test")

        # Create combined client with mock providers
        from resonance.core.provider_fusion import NamedProvider, CombinedProviderClient
        from resonance.core.identifier import ProviderCapabilities, ProviderRelease, ProviderTrack

        acoustid_client = AcoustIDClient()

        class MockMetadataClient:
            @property
            def capabilities(self) -> ProviderCapabilities:
                return ProviderCapabilities(supports_fingerprints=False, supports_metadata=True)

            def search_by_fingerprints(self, fingerprints):
                return []

            def search_by_metadata(self, artist, album, track_count):
                if artist == "Known Artist" and album == "Known Album":
                    return [ProviderRelease(
                        provider="metadata_provider",
                        release_id="meta-123",
                        title="Known Album",
                        artist="Known Artist",
                        tracks=(ProviderTrack(position=1, title="Track 1"),),
                    )]
                return []

        combined_client = CombinedProviderClient((
            NamedProvider("acoustid", acoustid_client),
            NamedProvider("metadata", MockMetadataClient()),
        ))

        # Test: AcoustID finds result, both providers may return candidates
        mock_acoustid_results = [
            {
                "score": 0.95,
                "recordings": [
                    {
                        "id": "recording-perfect",
                        "title": "Known Album",
                        "artists": [{"name": "Known Artist"}],
                    }
                ]
            }
        ]

        with patch('acoustid.lookup', return_value=mock_acoustid_results) as mock_lookup:
            result = identify(evidence, combined_client)

            # Should get results from both providers (AcoustID and metadata)
            assert len(result.candidates) >= 1
            # AcoustID should be present in results
            acoustid_candidates = [c for c in result.candidates if c.release.provider == "acoustid"]
            assert len(acoustid_candidates) == 1
            assert acoustid_candidates[0].release.title == "Known Album"

        # Test: AcoustID fails, metadata provides fallback
        with patch('acoustid.lookup', return_value=[]) as mock_lookup:
            result = identify(evidence, combined_client)

            # Should get result from metadata provider
            assert len(result.candidates) >= 1
            # Verify metadata was used as fallback
            providers_found = {c.release.provider for c in result.candidates}
            assert "metadata" in providers_found
