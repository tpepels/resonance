# tests/unit/test_services.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from resonance.core.models import AlbumInfo, TrackInfo, UserSkippedError
from resonance.services.release_search import ReleaseCandidate, ReleaseSearchService
from resonance.services.prompt_service import PromptService


def test_release_auto_select_picks_best_when_clear_lead():
    svc = ReleaseSearchService(musicbrainz=MagicMock(), discogs=None)
    candidates = [
        ReleaseCandidate(
            provider="musicbrainz",
            release_id="mbid-1",
            title="Album",
            artist="Artist",
            year=1999,
            track_count=10,
            score=0.92,
            coverage=0.92,
        ),
        ReleaseCandidate(
            provider="musicbrainz",
            release_id="mbid-2",
            title="Album",
            artist="Artist",
            year=1999,
            track_count=10,
            score=0.74,
            coverage=0.90,
        ),
    ]

    best = svc.auto_select_best(candidates, min_score=0.8, min_coverage=0.8)
    assert best is not None
    assert best.release_id == "mbid-1"


def test_release_auto_select_refuses_when_gap_is_small():
    svc = ReleaseSearchService(musicbrainz=MagicMock(), discogs=None)
    candidates = [
        ReleaseCandidate(
            provider="musicbrainz",
            release_id="mbid-1",
            title="Album",
            artist="Artist",
            year=1999,
            track_count=10,
            score=0.86,
            coverage=0.90,
        ),
        ReleaseCandidate(
            provider="musicbrainz",
            release_id="mbid-2",
            title="Album",
            artist="Artist",
            year=1999,
            track_count=10,
            score=0.75,
            coverage=0.90,
        ),
    ]

    best = svc.auto_select_best(candidates, min_score=0.8, min_coverage=0.8)
    assert best is None


def test_prompt_service_accepts_direct_ids(monkeypatch):
    prompt = PromptService(interactive=True)
    album = AlbumInfo(directory=Path("."))
    album.tracks = [TrackInfo(path=album.directory / "01.flac", title="Track", duration_seconds=180)]
    album.total_tracks = 1

    monkeypatch.setattr("builtins.input", lambda _: "mb:1234")
    result = prompt.prompt_for_release(album)
    assert result == ("musicbrainz", "1234")


def test_prompt_service_skip_raises(monkeypatch):
    prompt = PromptService(interactive=True)
    album = AlbumInfo(directory=Path("."))
    album.tracks = [TrackInfo(path=album.directory / "01.flac", title="Track", duration_seconds=180)]
    album.total_tracks = 1

    monkeypatch.setattr("builtins.input", lambda _: "s")
    with pytest.raises(UserSkippedError):
        prompt.prompt_for_release(album)
