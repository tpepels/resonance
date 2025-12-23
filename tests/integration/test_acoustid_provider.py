"""Integration tests for AcoustID provider fingerprint-based identification."""

from __future__ import annotations

import pytest

from resonance.core.identifier import DirectoryEvidence, TrackEvidence
from resonance.providers.acoustid import AcoustIDCache, AcoustIDClient


class TestAcoustIDProviderIntegration:
    """Test AcoustID provider integration with fingerprint evidence."""

    def test_acoustid_client_capabilities(self) -> None:
        """Test that AcoustID client declares correct capabilities."""
        client = AcoustIDClient()

        capabilities = client.capabilities
        assert capabilities.supports_fingerprints is True
        assert capabilities.supports_metadata is False  # AcoustID doesn't support metadata-only search

    def test_acoustid_search_by_fingerprints_empty(self) -> None:
        """Test that empty fingerprint list returns empty results."""
        client = AcoustIDClient()

        result = client.search_by_fingerprints([])
        assert result == []

    def test_acoustid_search_by_fingerprints_non_empty(self) -> None:
        """Test that non-empty fingerprint list is accepted."""
        from unittest.mock import patch

        client = AcoustIDClient()

        # Mock acoustid.lookup to return empty results (simulating no matches)
        with patch('acoustid.lookup', return_value=[]):
            result = client.search_by_fingerprints(["fp1", "fp2", "fp3"])
            assert result == []

    def test_acoustid_search_by_metadata_not_supported(self) -> None:
        """Test that metadata search is not supported and returns empty."""
        client = AcoustIDClient()

        result = client.search_by_metadata("Artist", "Album", 10)
        assert result == []

    def test_fingerprint_path_integration_with_evidence(self) -> None:
        """Integration test: fingerprints from DirectoryEvidence flow to AcoustID client."""
        from unittest.mock import patch

        # Create evidence with fingerprints
        evidence = DirectoryEvidence(
            tracks=(
                TrackEvidence(fingerprint_id="fp-track-1", duration_seconds=180),
                TrackEvidence(fingerprint_id="fp-track-2", duration_seconds=200),
                TrackEvidence(fingerprint_id="fp-track-3", duration_seconds=220),
            ),
            track_count=3,
            total_duration_seconds=600,
        )

        # Verify evidence has fingerprints
        assert evidence.has_fingerprints is True

        # Test that AcoustID client can be called with evidence fingerprints
        client = AcoustIDClient()
        fingerprints = [t.fingerprint_id for t in evidence.tracks if t.fingerprint_id]

        # Mock acoustid.lookup to avoid real API calls
        with patch('acoustid.lookup', return_value=[]):
            result = client.search_by_fingerprints(fingerprints)
            assert isinstance(result, list)

        # Verify fingerprints were passed correctly
        assert len(fingerprints) == 3
        assert "fp-track-1" in fingerprints
        assert "fp-track-2" in fingerprints
        assert "fp-track-3" in fingerprints

    def test_acoustid_cache_key_deterministic(self) -> None:
        """Test that cache keys are deterministic for same inputs."""
        # Test cache key generation
        key1 = AcoustIDCache.make_cache_key(["fp1", "fp2", "fp3"], "1.0")
        key2 = AcoustIDCache.make_cache_key(["fp1", "fp2", "fp3"], "1.0")
        key3 = AcoustIDCache.make_cache_key(["fp3", "fp2", "fp1"], "1.0")  # Different order

        # Same inputs should produce same key
        assert key1 == key2

        # Different order should produce same key (deterministic sorting)
        assert key1 == key3

        # Different client version should produce different key
        key4 = AcoustIDCache.make_cache_key(["fp1", "fp2", "fp3"], "1.1")
        assert key1 != key4

    def test_acoustid_cache_key_unique(self) -> None:
        """Test that different fingerprint sets produce different keys."""
        key1 = AcoustIDCache.make_cache_key(["fp1", "fp2"], "1.0")
        key2 = AcoustIDCache.make_cache_key(["fp1", "fp2", "fp3"], "1.0")
        key3 = AcoustIDCache.make_cache_key(["fp4", "fp5"], "1.0")

        # Different fingerprint sets should produce different keys
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_acoustid_client_initialization(self) -> None:
        """Test AcoustID client initialization with different parameters."""
        import os

        # Clear any existing ACOUSTID_API_KEY environment variable for this test
        original_key = os.environ.get("ACOUSTID_API_KEY")
        if "ACOUSTID_API_KEY" in os.environ:
            del os.environ["ACOUSTID_API_KEY"]

        try:
            # Default initialization (should not pick up env var since we cleared it)
            client1 = AcoustIDClient()
            assert client1.api_key is None
            assert client1.base_url == "https://api.acoustid.org/v2"

            # With API key
            client2 = AcoustIDClient(api_key="test-key")
            assert client2.api_key == "test-key"

            # With custom base URL
            client3 = AcoustIDClient(base_url="https://custom.api.com")
            assert client3.base_url == "https://custom.api.com"

            # All should have same capabilities
            for client in [client1, client2, client3]:
                assert client.capabilities.supports_fingerprints is True
                assert client.capabilities.supports_metadata is False
        finally:
            # Restore original environment variable if it existed
            if original_key is not None:
                os.environ["ACOUSTID_API_KEY"] = original_key
