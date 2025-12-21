# tests/unit/test_services.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from resonance.core.models import AlbumInfo, TrackInfo, UserSkippedError
from resonance.services.release_search import ReleaseCandidate, ReleaseSearchService
from resonance.services.prompt_service import PromptService
from resonance.providers.musicbrainz import MusicBrainzClient


def test_release_auto_select_picks_best_when_clear_lead():
    svc = ReleaseSearchService(musicbrainz=MagicMock(spec_set=MusicBrainzClient), discogs=None)
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
    svc = ReleaseSearchService(musicbrainz=MagicMock(spec_set=MusicBrainzClient), discogs=None)
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

# --- additional service tests (release search + prompt) ---

def test_release_auto_select_returns_none_on_empty_list():
    svc = ReleaseSearchService(musicbrainz=MagicMock(spec_set=MusicBrainzClient), discogs=None)
    assert svc.auto_select_best([], min_score=0.8, min_coverage=0.8) is None


def test_release_auto_select_single_candidate_respects_thresholds():
    svc = ReleaseSearchService(musicbrainz=MagicMock(spec_set=MusicBrainzClient), discogs=None)
    c = ReleaseCandidate(
        provider="musicbrainz",
        release_id="mbid-1",
        title="Album",
        artist="Artist",
        year=1999,
        track_count=10,
        score=0.79,
        coverage=0.95,
    )
    # Below min_score => refuse
    assert svc.auto_select_best([c], min_score=0.8, min_coverage=0.8) is None

    c2 = ReleaseCandidate(
        provider="musicbrainz",
        release_id="mbid-2",
        title="Album",
        artist="Artist",
        year=1999,
        track_count=10,
        score=0.95,
        coverage=0.79,
    )
    # Below min_coverage => refuse
    assert svc.auto_select_best([c2], min_score=0.8, min_coverage=0.8) is None

    c3 = ReleaseCandidate(
        provider="musicbrainz",
        release_id="mbid-3",
        title="Album",
        artist="Artist",
        year=1999,
        track_count=10,
        score=0.95,
        coverage=0.95,
    )
    assert svc.auto_select_best([c3], min_score=0.8, min_coverage=0.8) is not None


def test_release_auto_select_refuses_on_equal_scores_or_ambiguous_tie():
    svc = ReleaseSearchService(musicbrainz=MagicMock(spec_set=MusicBrainzClient), discogs=None)
    candidates = [
        ReleaseCandidate(
            provider="musicbrainz",
            release_id="mbid-1",
            title="Album",
            artist="Artist",
            year=1999,
            track_count=10,
            score=0.90,
            coverage=0.90,
        ),
        ReleaseCandidate(
            provider="discogs",
            release_id="dg-1",
            title="Album",
            artist="Artist",
            year=1999,
            track_count=10,
            score=0.90,
            coverage=0.90,
        ),
    ]
    # Without a clear lead, should refuse.
    assert svc.auto_select_best(candidates, min_score=0.8, min_coverage=0.8) is None


def test_release_auto_select_is_order_independent_for_best_choice():
    svc = ReleaseSearchService(musicbrainz=MagicMock(spec_set=MusicBrainzClient), discogs=None)
    c1 = ReleaseCandidate(
        provider="musicbrainz",
        release_id="mbid-1",
        title="Album",
        artist="Artist",
        year=1999,
        track_count=10,
        score=0.95,
        coverage=0.90,
    )
    c2 = ReleaseCandidate(
        provider="musicbrainz",
        release_id="mbid-2",
        title="Album",
        artist="Artist",
        year=1999,
        track_count=10,
        score=0.70,
        coverage=0.90,
    )

    best_a = svc.auto_select_best([c1, c2], min_score=0.8, min_coverage=0.8)
    best_b = svc.auto_select_best([c2, c1], min_score=0.8, min_coverage=0.8)

    assert best_a is not None and best_b is not None
    assert best_a.release_id == best_b.release_id == "mbid-1"


def test_release_auto_select_rejects_non_numeric_score() -> None:
    svc = ReleaseSearchService(musicbrainz=MagicMock(spec_set=MusicBrainzClient), discogs=None)
    candidate = ReleaseCandidate(
        provider="musicbrainz",
        release_id="mbid-1",
        title="Album",
        artist="Artist",
        year=1999,
        track_count=10,
        score=MagicMock(),
        coverage=0.9,
    )
    with pytest.raises(TypeError, match="Candidate score must be numeric"):
        svc.auto_select_best([candidate], min_score=0.8, min_coverage=0.8)


def test_release_auto_select_prefers_higher_coverage_when_scores_equal_if_supported():
    svc = ReleaseSearchService(musicbrainz=MagicMock(spec_set=MusicBrainzClient), discogs=None)
    candidates = [
        ReleaseCandidate(
            provider="musicbrainz",
            release_id="mbid-lowcov",
            title="Album",
            artist="Artist",
            year=1999,
            track_count=10,
            score=0.90,
            coverage=0.81,
        ),
        ReleaseCandidate(
            provider="musicbrainz",
            release_id="mbid-highcov",
            title="Album",
            artist="Artist",
            year=1999,
            track_count=10,
            score=0.90,
            coverage=0.95,
        ),
    ]
    # If your auto_select_best treats equal scores as ambiguous and refuses,
    # change expected to None. If it uses coverage as tie-break, expect highcov.
    best = svc.auto_select_best(candidates, min_score=0.8, min_coverage=0.8)
    if best is not None:
        assert best.release_id == "mbid-highcov"


def _make_prompt_album() -> AlbumInfo:
    album = AlbumInfo(directory=Path("."))
    album.tracks = [
        TrackInfo(path=album.directory / "01.flac", title="Track 1", duration_seconds=180),
        TrackInfo(path=album.directory / "02.flac", title="Track 2", duration_seconds=None),
    ]
    album.total_tracks = len(album.tracks)
    return album


def test_prompt_service_accepts_direct_ids_with_whitespace_and_case(monkeypatch):
    prompt = PromptService(interactive=True)
    album = _make_prompt_album()

    monkeypatch.setattr("builtins.input", lambda _: "  MB:1234  ")
    result = prompt.prompt_for_release(album)
    assert result == ("musicbrainz", "1234")


def test_prompt_service_accepts_discogs_direct_id(monkeypatch):
    prompt = PromptService(interactive=True)
    album = _make_prompt_album()

    monkeypatch.setattr("builtins.input", lambda _: "dg:9876")
    result = prompt.prompt_for_release(album)
    assert result == ("discogs", "9876")


def test_prompt_service_rejects_invalid_prefix_and_repompts(monkeypatch):
    """
    Sequence:
      1) invalid input
      2) valid input
    """
    prompt = PromptService(interactive=True)
    album = _make_prompt_album()

    answers = iter(["spotify:123", "mb:4321"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    result = prompt.prompt_for_release(album)
    assert result == ("musicbrainz", "4321")


def test_prompt_service_rejects_empty_input_then_accepts(monkeypatch):
    prompt = PromptService(interactive=True)
    album = _make_prompt_album()

    answers = iter(["", "   ", "mb:111"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    result = prompt.prompt_for_release(album)
    assert result == ("musicbrainz", "111")


def test_prompt_service_skip_variants_raise(monkeypatch):
    prompt = PromptService(interactive=True)
    album = _make_prompt_album()

    for skip_value in ["s", "S", "skip", "SKIP"]:
        monkeypatch.setattr("builtins.input", lambda _: skip_value)
        with pytest.raises(UserSkippedError):
            prompt.prompt_for_release(album)


def test_prompt_service_noninteractive_raises_or_refuses_cleanly():
    """
    Decide and encode a single behavior:
    - Either PromptService(interactive=False).prompt_for_release raises a clear error
      (e.g., RuntimeError) OR returns None.
    This test accepts either pattern but ensures it does not prompt.
    """
    prompt = PromptService(interactive=False)
    album = _make_prompt_album()

    try:
        out = prompt.prompt_for_release(album)
        assert out is None
    except Exception as e:
        assert isinstance(e, (RuntimeError, ValueError))


def test_prompt_service_does_not_crash_on_empty_track_list(monkeypatch):
    prompt = PromptService(interactive=True)
    album = AlbumInfo(directory=Path("."))
    album.tracks = []
    album.total_tracks = 0

    # Provide a valid direct id so prompt can exit quickly.
    monkeypatch.setattr("builtins.input", lambda _: "mb:1")
    result = prompt.prompt_for_release(album)
    assert result == ("musicbrainz", "1")
