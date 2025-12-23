"""Integration tests for metadata channel functionality in V3.05.

Tests the complete metadata search flow:
1. Tag extraction from audio files
2. Artist/album hint extraction
3. MusicBrainz metadata search
4. Provider result processing
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch, PropertyMock

import pytest

from resonance.core.identifier import DirectoryEvidence, TrackEvidence, ProviderCapabilities, identify
from resonance.providers.musicbrainz import MusicBrainzClient


class MockMusicBrainzClient(MusicBrainzClient):
    """Test client that supports metadata search."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=False,
            supports_metadata=True,
        )


def test_metadata_channel_tag_extraction(tmp_path: Path) -> None:
    """Test that artist/album hints are extracted from existing tags."""
    # Create a test audio file with metadata
    audio_file = tmp_path / "track.flac"
    audio_file.write_text("fake audio")

    # Create metadata with artist/album tags
    meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
    meta_file.write_text('''{
        "duration_seconds": 180,
        "tags": {
            "artist": "Test Artist",
            "album": "Test Album",
            "track_number": "1"
        }
    }''')

    # Create evidence
    from resonance.core.identifier import extract_evidence
    evidence = extract_evidence([audio_file])

    # Verify tags were extracted
    assert len(evidence.tracks) == 1
    track = evidence.tracks[0]
    assert track.existing_tags["artist"] == "Test Artist"
    assert track.existing_tags["album"] == "Test Album"

    # Test metadata search hint extraction
    client = MockMusicBrainzClient()

    with patch.object(client, 'search_by_metadata', return_value=[]) as mock_search:
        identify(evidence, client)

        # Verify search was called with extracted hints
        mock_search.assert_called_once_with("Test Artist", "Test Album", 1)


def test_metadata_channel_albumartist_preference(tmp_path: Path) -> None:
    """Test that albumartist is preferred over artist for metadata search."""
    audio_file = tmp_path / "track.flac"
    audio_file.write_text("fake audio")

    # Create metadata with both albumartist and artist
    meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
    meta_file.write_text('''{
        "duration_seconds": 180,
        "tags": {
            "artist": "Track Artist",
            "albumartist": "Album Artist",
            "album": "Test Album"
        }
    }''')

    from resonance.core.identifier import extract_evidence
    evidence = extract_evidence([audio_file])

    client = MockMusicBrainzClient()

    with patch.object(client, 'search_by_metadata', return_value=[]) as mock_search:
        identify(evidence, client)

        # Should prefer albumartist over artist
        mock_search.assert_called_once_with("Album Artist", "Test Album", 1)


def test_metadata_channel_case_insensitive_tags(tmp_path: Path) -> None:
    """Test that tag extraction works with different case variations."""
    audio_file = tmp_path / "track.flac"
    audio_file.write_text("fake audio")

    # Create metadata with uppercase tag names (common in some formats)
    meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
    meta_file.write_text('''{
        "duration_seconds": 180,
        "tags": {
            "ARTIST": "Test Artist",
            "ALBUM": "Test Album"
        }
    }''')

    from resonance.core.identifier import extract_evidence
    evidence = extract_evidence([audio_file])

    client = MockMusicBrainzClient()

    with patch.object(client, 'search_by_metadata', return_value=[]) as mock_search:
        identify(evidence, client)

        # Should extract from uppercase tags
        mock_search.assert_called_once_with("Test Artist", "Test Album", 1)


def test_metadata_channel_anti_placeholder_guard(tmp_path: Path) -> None:
    """Test that metadata search fails when tags exist but no hints extracted."""
    audio_file = tmp_path / "track.flac"
    audio_file.write_text("fake audio")

    # Create metadata with tags but no artist/album
    meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
    meta_file.write_text('''{
        "duration_seconds": 180,
        "tags": {
            "title": "Test Track",
            "genre": "Rock"
        }
    }''')

    from resonance.core.identifier import extract_evidence
    evidence = extract_evidence([audio_file])

    client = MockMusicBrainzClient()

    # Should raise ValueError due to anti-placeholder guard
    with pytest.raises(ValueError, match="Tags exist but no artist/album hints extracted"):
        identify(evidence, client)


def test_metadata_channel_multiple_tracks_consistent(tmp_path: Path) -> None:
    """Test that metadata hints are taken from first track consistently."""
    # Create multiple tracks with different metadata
    tracks = []
    for i in range(3):
        audio_file = tmp_path / f"track{i+1}.flac"
        audio_file.write_text("fake audio")

        meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
        meta_file.write_text(f'''{{
            "duration_seconds": 180,
            "tags": {{
                "artist": "Track Artist {i+1}",
                "album": "Album {i+1}",
                "track_number": "{i+1}"
            }}
        }}''')
        tracks.append(audio_file)

    from resonance.core.identifier import extract_evidence
    evidence = extract_evidence(tracks)

    client = MockMusicBrainzClient()

    with patch.object(client, 'search_by_metadata', return_value=[]) as mock_search:
        identify(evidence, client)

        # Should use hints from first track only
        mock_search.assert_called_once_with("Track Artist 1", "Album 1", 3)


def test_metadata_channel_provider_integration(tmp_path: Path) -> None:
    """Integration test: metadata channel produces candidates from MusicBrainz."""
    audio_file = tmp_path / "track.flac"
    audio_file.write_text("fake audio")

    meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
    meta_file.write_text('''{
        "duration_seconds": 180,
        "tags": {
            "artist": "The Beatles",
            "album": "Abbey Road"
        }
    }''')

    from resonance.core.identifier import extract_evidence
    evidence = extract_evidence([audio_file])

    # Create a mock MusicBrainz client that returns a fake release
    from resonance.core.identifier import ProviderRelease, ProviderTrack

    mock_release = ProviderRelease(
        provider="musicbrainz",
        release_id="test-release-123",
        title="Abbey Road",
        artist="The Beatles",
        tracks=(
            ProviderTrack(position=1, title="Come Together", duration_seconds=180),
        ),
    )

    client = MockMusicBrainzClient()

    with patch.object(client, 'search_by_metadata', return_value=[mock_release]) as mock_search:
        result = identify(evidence, client)

        # Verify search was called
        mock_search.assert_called_once_with("The Beatles", "Abbey Road", 1)

        # Verify we got a result
        assert len(result.candidates) == 1
        assert result.candidates[0].release.title == "Abbey Road"
        assert result.candidates[0].release.artist == "The Beatles"
