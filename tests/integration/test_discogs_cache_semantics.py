"""E2E cache semantics for Discogs provider wrapper."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse
import urllib.request

import pytest

from resonance.errors import RuntimeFailure
from resonance.infrastructure.cache import MetadataCache
from resonance.providers.caching import CachedProviderClient, ProviderConfig
from resonance.providers.discogs import DiscogsClient


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _load_fixture(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "discogs" / name
    return json.loads(path.read_text())


def test_discogs_cached_provider_avoids_second_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = MetadataCache(tmp_path / "cache.db")
    search_payload = _load_fixture("search_results.json")
    release_100 = _load_fixture("release_100.json")
    release_200 = _load_fixture("release_200.json")
    calls = {"count": 0}

    def fake_urlopen(request, timeout=10):
        calls["count"] += 1
        url = request.full_url if hasattr(request, "full_url") else str(request)
        parsed = urlparse(url)
        if parsed.path.endswith("/database/search"):
            return _FakeResponse(search_payload)
        if parsed.path.endswith("/releases/100"):
            return _FakeResponse(release_100)
        if parsed.path.endswith("/releases/200"):
            return _FakeResponse(release_200)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = DiscogsClient(token="token", cache=cache, offline=False)
    cached = CachedProviderClient(
        client,
        cache,
        ProviderConfig(provider_name="discogs", client_version="1.0.0", offline=False),
    )

    result1 = cached.search_by_metadata("Artist One", "Album One", track_count=1)
    assert [entry.release_id for entry in result1] == ["100", "200"]
    assert calls["count"] > 0

    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("HTTP call should not occur on cache hit")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)

    result2 = cached.search_by_metadata("Artist One", "Album One", track_count=1)
    assert [entry.release_id for entry in result2] == ["100", "200"]

    cached_offline = CachedProviderClient(
        client,
        cache,
        ProviderConfig(provider_name="discogs", client_version="1.0.0", offline=True),
    )
    result3 = cached_offline.search_by_metadata("Artist One", "Album One", track_count=1)
    assert [entry.release_id for entry in result3] == ["100", "200"]

    cache.close()


def test_discogs_offline_cache_miss_raises(tmp_path: Path) -> None:
    cache = MetadataCache(tmp_path / "cache.db")
    client = DiscogsClient(token="token", cache=cache, offline=False)
    cached_offline = CachedProviderClient(
        client,
        cache,
        ProviderConfig(provider_name="discogs", client_version="1.0.0", offline=True),
    )

    with pytest.raises(RuntimeFailure, match="requires network.*offline mode.*cache miss"):
        cached_offline.search_by_metadata("Artist One", "Album One", track_count=1)

    cache.close()
