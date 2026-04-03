"""Unit tests for MusicBrainz client release parsing and retries."""

from __future__ import annotations

import json
from pathlib import Path
import urllib.error

from resonance.legacy.musicbrainz import MusicBrainzClient


def _load_fixture(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "musicbrainz" / name
    return json.loads(path.read_text())


def test_musicbrainz_build_release_multi_medium() -> None:
    payload = _load_fixture("release_multi_medium.json")
    client = MusicBrainzClient(acoustid_api_key="key", offline=True)
    release = client._build_release_data(payload)

    assert release.release_id == "mb-release-1"
    assert release.album_title == "Multi Medium Album"
    assert release.album_artist == "Artist MM"
    assert release.release_date == "1999-05-01"
    assert release.disc_count == 2
    assert release.formats == ["CD"]
    assert len(release.tracks) == 3
    assert release.tracks[0].disc_number == 1
    assert release.tracks[2].disc_number == 2


def test_musicbrainz_build_release_missing_date() -> None:
    payload = _load_fixture("release_missing_date.json")
    client = MusicBrainzClient(acoustid_api_key="key", offline=True)
    release = client._build_release_data(payload)

    assert release.release_id == "mb-release-2"
    assert release.release_date is None
    assert release.formats == ["Vinyl"]
    assert release.tracks[0].number == 1


def test_musicbrainz_retry_transient_error_returns_none() -> None:
    client = MusicBrainzClient(acoustid_api_key="key", network_retries=0, offline=False)

    def failing():
        raise urllib.error.URLError("rate limit")

    result = client._run_with_retries(failing, "MusicBrainz fetch", Path("mb-release"))
    assert result is None
