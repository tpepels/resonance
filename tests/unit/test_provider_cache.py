"""Unit tests for provider cache key and serialization stability."""

from __future__ import annotations

from resonance.infrastructure.provider_cache import (
    build_cache_key,
    canonical_json,
    provider_cache_key,
    provider_cache_relevant_settings,
)


def test_build_cache_key_stable() -> None:
    key = build_cache_key(
        provider="musicbrainz",
        request_type="release",
        query={"artist": "Artist", "title": "Album"},
        version="v1",
    )
    assert key == "musicbrainz:release:v1:artist=Artist|title=Album"


def test_build_cache_key_normalizes_query_order() -> None:
    key1 = build_cache_key(
        provider="discogs",
        request_type="search",
        query={"b": "2", "a": "1"},
        version="v2",
    )
    key2 = build_cache_key(
        provider="discogs",
        request_type="search",
        query={"a": "1", "b": "2"},
        version="v2",
    )
    assert key1 == key2


def test_canonical_json_stable() -> None:
    payload = {"b": [2, 1], "a": {"y": 2, "x": 1}}
    assert canonical_json(payload) == '{"a":{"x":1,"y":2},"b":[2,1]}'


def test_canonical_json_preserves_list_order() -> None:
    payload = {
        "items": [
            {"id": 2, "name": "b"},
            {"id": 1, "name": "a"},
        ],
    }
    assert canonical_json(payload) == (
        '{"items":[{"id":2,"name":"b"},{"id":1,"name":"a"}]}'
    )


def test_provider_cache_key_includes_client_version() -> None:
    key = provider_cache_key(
        provider="musicbrainz",
        request_type="release",
        query={"id": "mb-1"},
        version="v1",
        client_version="2.0.0",
    )
    assert key == "musicbrainz:release:v1:2.0.0:id=mb-1"


def test_provider_cache_key_changes_with_client_version() -> None:
    key1 = provider_cache_key(
        provider="discogs",
        request_type="search",
        query={"q": "Album"},
        version="v1",
        client_version="1.0.0",
    )
    key2 = provider_cache_key(
        provider="discogs",
        request_type="search",
        query={"q": "Album"},
        version="v1",
        client_version="1.1.0",
    )
    assert key1 != key2


def test_settings_hash_irrelevant_changes_do_not_affect_provider_cache() -> None:
    relevant = provider_cache_relevant_settings(
        {"library_root": "/music", "offline": False}
    )
    changed = provider_cache_relevant_settings(
        {"library_root": "/other", "offline": False}
    )
    assert relevant == changed
