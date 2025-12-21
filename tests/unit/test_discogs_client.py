"""Unit tests for Discogs client fixtures and determinism."""

from __future__ import annotations

import json
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlparse

import pytest

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


def test_discogs_search_returns_stable_order(monkeypatch: pytest.MonkeyPatch) -> None:
    search_payload = _load_fixture("search_results.json")
    release_100 = _load_fixture("release_100.json")
    release_200 = _load_fixture("release_200.json")

    def fake_urlopen(request, timeout=10):
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

    client = DiscogsClient(token="token")
    results = client.search_releases(artist="Artist One", album="Album One")
    assert [entry["id"] for entry in results] == [100, 200]
    assert results[0]["track_count"] == 1
    assert results[1]["track_count"] == 2


def test_discogs_search_handles_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    search_payload = _load_fixture("search_results_empty.json")

    def fake_urlopen(request, timeout=10):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        parsed = urlparse(url)
        if parsed.path.endswith("/database/search"):
            return _FakeResponse(search_payload)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = DiscogsClient(token="token")
    results = client.search_releases(artist="Artist One", album="Album One")
    assert results == []


def test_discogs_search_handles_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            url="https://api.discogs.com/database/search",
            code=429,
            msg="rate limited",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = DiscogsClient(token="token")
    results = client.search_releases(artist="Artist One", album="Album One")
    assert results == []


def test_discogs_release_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*_args, **_kwargs):
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = DiscogsClient(token="token")
    assert client.get_release(100) is None


def test_discogs_parses_track_positions() -> None:
    client = DiscogsClient(token="token")
    assert client._parse_track_number("1") == 1
    assert client._parse_track_number("1-03") == 3
    assert client._parse_track_number("2/04") == 4
    assert client._parse_track_number("A") == 1
    assert client._parse_track_number("B2") == 2


def test_discogs_joins_artist_names() -> None:
    client = DiscogsClient(token="token")
    artists = [
        {"name": "Artist One"},
        {"name": "Artist One (2)"},
        {"name": "Artist Two"},
        {"name": "Artist Two"},
    ]
    assert client._join_artists(artists) == "Artist One, Artist Two"
