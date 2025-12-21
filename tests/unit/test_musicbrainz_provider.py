"""Unit tests for MusicBrainz provider client."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resonance.providers.musicbrainz import MusicBrainzClient


class _FakeMusicBrainz:
    def __init__(self, releases: dict[str, dict]) -> None:
        self._releases = releases
        self.useragent_calls: list[tuple[str, str, str | None]] = []

    def set_useragent(self, app: str, version: str, contact: str | None = None) -> None:
        self.useragent_calls.append((app, version, contact))

    def search_releases(self, **_kwargs):
        return {"release-list": [{"id": release_id} for release_id in self._releases]}

    def get_release_by_id(self, release_id: str, includes=None):
        _ = includes
        return {"release": self._releases[release_id]}


def _load_fixture(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "musicbrainz" / name
    return json.loads(path.read_text())


def test_musicbrainz_multi_medium_and_missing_date(monkeypatch: pytest.MonkeyPatch) -> None:
    release_multi = _load_fixture("release_multi_medium.json")
    release_missing = _load_fixture("release_missing_date.json")
    fake = _FakeMusicBrainz(
        {
            release_multi["id"]: release_multi,
            release_missing["id"]: release_missing,
        }
    )

    monkeypatch.setattr("resonance.providers.musicbrainz.musicbrainzngs", fake)

    client = MusicBrainzClient(useragent="test@example.com")
    results = client.search_by_metadata(artist="Artist", album="Album", track_count=3)

    assert [entry.release_id for entry in results] == ["mb-release-1", "mb-release-2"]

    multi = results[0]
    assert multi.title == "Multi Medium Album"
    assert multi.artist == "Artist MM"
    assert multi.year == 1999
    assert multi.track_count == 3
    assert multi.tracks[0].disc_number == 1
    assert multi.tracks[2].disc_number == 2
    assert multi.tracks[0].duration_seconds == 180
    assert multi.tracks[0].recording_id == "rec-1"
    assert multi.release_kind == "ep"

    missing = results[1]
    assert missing.year is None
    assert missing.tracks[0].position == 1
    assert missing.release_kind == "single"
