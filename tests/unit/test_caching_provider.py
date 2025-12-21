"""Unit tests for CachedProviderClient wrapper.

Phase C.3 acceptance criteria:
- Test can assert: "second run performs zero HTTP calls"
- Test can assert: "offline mode never attempts network"
- Test can assert: "offline + cache hit works"
- Test can assert: "offline + cache miss yields deterministic error"
"""

from __future__ import annotations

import pytest

from resonance.core.identifier import ProviderClient, ProviderRelease, ProviderTrack
from resonance.errors import RuntimeFailure
from resonance.infrastructure.cache import MetadataCache
from resonance.providers.caching import CachedProviderClient, ProviderConfig


class _StubProvider:
    """Stub provider that tracks how many times it was called."""

    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = releases
        self.fingerprint_call_count = 0
        self.metadata_call_count = 0

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        self.fingerprint_call_count += 1
        # Filter releases that match fingerprints
        matching = [
            r
            for r in self._releases
            if any(
                track.fingerprint_id in fingerprints
                for track in r.tracks
                if track.fingerprint_id
            )
        ]
        return matching

    def search_by_metadata(
        self, artist: str | None, album: str | None, track_count: int
    ) -> list[ProviderRelease]:
        self.metadata_call_count += 1
        # Simple matching: artist/album match
        matching = [
            r
            for r in self._releases
            if (artist is None or r.artist == artist)
            and (album is None or r.title == album)
        ]
        return matching


def _make_release(
    provider: str = "test",
    release_id: str = "test-1",
    title: str = "Test Album",
    artist: str = "Test Artist",
    tracks: tuple[ProviderTrack, ...] = (),
    release_kind: str | None = None,
) -> ProviderRelease:
    """Helper to create ProviderRelease."""
    return ProviderRelease(
        provider=provider,
        release_id=release_id,
        title=title,
        artist=artist,
        tracks=tracks,
        year=2020,
        release_kind=release_kind,
    )


def test_search_by_fingerprints_caches_result(tmp_path) -> None:
    """First call hits provider, second call uses cache (zero HTTP calls)."""
    cache = MetadataCache(tmp_path / "cache.db")
    release = _make_release(
        tracks=(
            ProviderTrack(
                position=1,
                title="Track 1",
                duration_seconds=180,
                fingerprint_id="fp-123",
            ),
        )
    )
    stub = _StubProvider([release])
    config = ProviderConfig(provider_name="test", client_version="1.0.0")

    client = CachedProviderClient(stub, cache, config)

    # First call - should hit provider
    result1 = client.search_by_fingerprints(["fp-123"])
    assert len(result1) == 1
    assert result1[0].release_id == "test-1"
    assert stub.fingerprint_call_count == 1

    # Second call - should use cache, NO provider call
    result2 = client.search_by_fingerprints(["fp-123"])
    assert len(result2) == 1
    assert result2[0].release_id == "test-1"
    assert stub.fingerprint_call_count == 1  # Still 1 - no new call

    cache.close()


def test_search_by_metadata_caches_result(tmp_path) -> None:
    """First call hits provider, second call uses cache (zero HTTP calls)."""
    cache = MetadataCache(tmp_path / "cache.db")
    release = _make_release(artist="Artist A", title="Album B")
    stub = _StubProvider([release])
    config = ProviderConfig(provider_name="test", client_version="1.0.0")

    client = CachedProviderClient(stub, cache, config)

    # First call - should hit provider
    result1 = client.search_by_metadata("Artist A", "Album B", track_count=10)
    assert len(result1) == 1
    assert result1[0].release_id == "test-1"
    assert stub.metadata_call_count == 1

    # Second call - should use cache, NO provider call
    result2 = client.search_by_metadata("Artist A", "Album B", track_count=10)
    assert len(result2) == 1
    assert result2[0].release_id == "test-1"
    assert stub.metadata_call_count == 1  # Still 1 - no new call

    cache.close()


def test_offline_mode_cache_hit_works(tmp_path) -> None:
    """Offline mode + cache hit → returns cached result."""
    cache = MetadataCache(tmp_path / "cache.db")
    release = _make_release(
        tracks=(
            ProviderTrack(
                position=1,
                title="Track 1",
                duration_seconds=180,
                fingerprint_id="fp-123",
            ),
        )
    )
    stub = _StubProvider([release])
    config_online = ProviderConfig(provider_name="test", client_version="1.0.0", offline=False)
    config_offline = ProviderConfig(provider_name="test", client_version="1.0.0", offline=True)

    # First: populate cache in online mode
    client_online = CachedProviderClient(stub, cache, config_online)
    result1 = client_online.search_by_fingerprints(["fp-123"])
    assert len(result1) == 1
    assert stub.fingerprint_call_count == 1

    # Second: use cache in offline mode (cache hit → success)
    client_offline = CachedProviderClient(stub, cache, config_offline)
    result2 = client_offline.search_by_fingerprints(["fp-123"])
    assert len(result2) == 1
    assert result2[0].release_id == "test-1"
    assert stub.fingerprint_call_count == 1  # No new call

    cache.close()


def test_offline_mode_cache_miss_raises_error(tmp_path) -> None:
    """Offline mode + cache miss → deterministic 'needs network' error."""
    cache = MetadataCache(tmp_path / "cache.db")
    release = _make_release()
    stub = _StubProvider([release])
    config = ProviderConfig(provider_name="test", client_version="1.0.0", offline=True)

    client = CachedProviderClient(stub, cache, config)

    # Offline mode + cache miss → error (never attempts network)
    with pytest.raises(RuntimeFailure, match="requires network.*offline mode.*cache miss"):
        client.search_by_fingerprints(["fp-missing"])

    # Verify provider was NEVER called
    assert stub.fingerprint_call_count == 0

    cache.close()


def test_offline_mode_never_calls_provider_on_cache_miss_metadata(tmp_path) -> None:
    """Offline mode + cache miss (metadata search) → error, no provider call."""
    cache = MetadataCache(tmp_path / "cache.db")
    release = _make_release()
    stub = _StubProvider([release])
    config = ProviderConfig(provider_name="test", client_version="1.0.0", offline=True)

    client = CachedProviderClient(stub, cache, config)

    # Offline mode + cache miss → error
    with pytest.raises(RuntimeFailure, match="requires network.*offline mode.*cache miss"):
        client.search_by_metadata("Missing Artist", "Missing Album", track_count=10)

    # Verify provider was NEVER called
    assert stub.metadata_call_count == 0

    cache.close()


def test_cache_key_stable_regardless_of_fingerprint_order(tmp_path) -> None:
    """Cache key is stable even if fingerprints are provided in different order."""
    cache = MetadataCache(tmp_path / "cache.db")
    release = _make_release(
        tracks=(
            ProviderTrack(
                position=1,
                title="Track 1",
                duration_seconds=180,
                fingerprint_id="fp-1",
            ),
            ProviderTrack(
                position=2,
                title="Track 2",
                duration_seconds=180,
                fingerprint_id="fp-2",
            ),
        )
    )
    stub = _StubProvider([release])
    config = ProviderConfig(provider_name="test", client_version="1.0.0")

    client = CachedProviderClient(stub, cache, config)

    # First call: fps in order [fp-1, fp-2]
    result1 = client.search_by_fingerprints(["fp-1", "fp-2"])
    assert stub.fingerprint_call_count == 1

    # Second call: fps in REVERSE order [fp-2, fp-1]
    # Should use cache (key is stable because we sort fingerprints)
    result2 = client.search_by_fingerprints(["fp-2", "fp-1"])
    assert stub.fingerprint_call_count == 1  # No new call - cache hit

    cache.close()


def test_client_version_invalidates_cache(tmp_path) -> None:
    """Changing client_version invalidates cache (new implementation)."""
    cache = MetadataCache(tmp_path / "cache.db")
    release = _make_release()
    stub = _StubProvider([release])
    config_v1 = ProviderConfig(provider_name="test", client_version="1.0.0")
    config_v2 = ProviderConfig(provider_name="test", client_version="2.0.0")

    # First: cache with client_version=1.0.0
    client_v1 = CachedProviderClient(stub, cache, config_v1)
    result1 = client_v1.search_by_metadata("Test Artist", "Test Album", track_count=10)
    assert stub.metadata_call_count == 1

    # Second: client_version=2.0.0 → cache miss (different version)
    client_v2 = CachedProviderClient(stub, cache, config_v2)
    result2 = client_v2.search_by_metadata("Test Artist", "Test Album", track_count=10)
    assert stub.metadata_call_count == 2  # New call - cache miss

    cache.close()


def test_cache_version_invalidates_cache(tmp_path) -> None:
    """Changing cache_version invalidates cache (DTO shape changed)."""
    cache = MetadataCache(tmp_path / "cache.db")
    release = _make_release()
    stub = _StubProvider([release])
    config_v1 = ProviderConfig(provider_name="test", client_version="1.0.0", cache_version="v1")
    config_v2 = ProviderConfig(provider_name="test", client_version="1.0.0", cache_version="v2")

    # First: cache with cache_version=v1
    client_v1 = CachedProviderClient(stub, cache, config_v1)
    result1 = client_v1.search_by_metadata("Test Artist", "Test Album", track_count=10)
    assert stub.metadata_call_count == 1

    # Second: cache_version=v2 → cache miss (different schema)
    client_v2 = CachedProviderClient(stub, cache, config_v2)
    result2 = client_v2.search_by_metadata("Test Artist", "Test Album", track_count=10)
    assert stub.metadata_call_count == 2  # New call - cache miss

    cache.close()


def test_serialization_roundtrip_preserves_data(tmp_path) -> None:
    """Cached data can be deserialized without loss."""
    cache = MetadataCache(tmp_path / "cache.db")
    release = _make_release(
        provider="discogs",
        release_id="discogs-12345",
        title="Original Album",
        artist="Original Artist",
        tracks=(
            ProviderTrack(
                position=1,
                title="Track One",
                duration_seconds=240,
                fingerprint_id="fp-abc",
            ),
            ProviderTrack(
                position=2,
                title="Track Two",
                duration_seconds=180,
                fingerprint_id=None,  # No fingerprint
            ),
        ),
        release_kind="ep",
    )
    stub = _StubProvider([release])
    config = ProviderConfig(provider_name="discogs", client_version="1.0.0")

    client = CachedProviderClient(stub, cache, config)

    # First call - writes to cache
    result1 = client.search_by_metadata("Original Artist", "Original Album", track_count=2)

    # Second call - reads from cache
    result2 = client.search_by_metadata("Original Artist", "Original Album", track_count=2)

    # Verify all fields preserved
    assert len(result2) == 1
    r = result2[0]
    assert r.provider == "discogs"
    assert r.release_id == "discogs-12345"
    assert r.title == "Original Album"
    assert r.artist == "Original Artist"
    assert r.year == 2020
    assert r.release_kind == "ep"
    assert len(r.tracks) == 2
    assert r.tracks[0].position == 1
    assert r.tracks[0].title == "Track One"
    assert r.tracks[0].fingerprint_id == "fp-abc"
    assert r.tracks[1].position == 2
    assert r.tracks[1].title == "Track Two"
    assert r.tracks[1].fingerprint_id is None

    cache.close()
