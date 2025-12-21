"""Unit tests for provider offline caching behavior."""

from __future__ import annotations

from pathlib import Path
import urllib.request

import pytest

from resonance.infrastructure.cache import MetadataCache
from resonance.providers.discogs import DiscogsClient


def test_discogs_offline_uses_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_path = tmp_path / "cache.db"
    cache = MetadataCache(cache_path)
    try:
        cached = {"id": 123, "title": "Album"}
        cache.set_discogs_release(
            "123",
            cached,
            cache_version="v1",
            client_version="0.1.0",
        )

        called = {"value": False}

        def fake_urlopen(*_args, **_kwargs):
            called["value"] = True
            raise AssertionError("network call should be skipped in offline mode")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        client = DiscogsClient(token="token", cache=cache, offline=True)
        assert client.get_release(123) == cached
        assert called["value"] is False
    finally:
        cache.close()


def test_discogs_offline_cache_miss_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cache.db"
    cache = MetadataCache(cache_path)
    try:
        called = {"value": False}

        def fake_urlopen(*_args, **_kwargs):
            called["value"] = True
            raise AssertionError("network call should be skipped in offline mode")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        client = DiscogsClient(token="token", cache=cache, offline=True)
        assert client.get_release(999) is None
        assert called["value"] is False
    finally:
        cache.close()
