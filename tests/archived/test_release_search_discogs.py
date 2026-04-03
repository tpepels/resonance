"""Unit tests for Discogs release scoring heuristics."""

from __future__ import annotations

from dataclasses import dataclass

from resonance.legacy.release_search import ReleaseSearchService


@dataclass
class _Track:
    musicbrainz_release_id: str | None = None


@dataclass
class _Album:
    canonical_artist: str | None
    canonical_composer: str | None
    canonical_album: str | None
    year: int | None
    tracks: list[_Track]


class _StubDiscogs:
    def __init__(self, results: list[dict]) -> None:
        self._results = results

    def search_releases(self, artist, album, title=None):
        return list(self._results)


def test_discogs_scores_exact_artist_album_match() -> None:
    album = _Album(
        canonical_artist="Artist One",
        canonical_composer=None,
        canonical_album="Album One",
        year=None,
        tracks=[_Track() for _ in range(10)],
    )
    releases = [
        {
            "id": 1,
            "title": "Album One",
            "artist": "Artist One",
            "year": 2001,
            "track_count": 10,
        },
        {
            "id": 2,
            "title": "Album Two",
            "artist": "Artist Two",
            "year": 2002,
            "track_count": 8,
        },
    ]
    svc = ReleaseSearchService(musicbrainz=None, discogs=_StubDiscogs(releases))
    candidates = svc._search_discogs_releases(album)
    assert [c.release_id for c in candidates] == ["1", "2"]
    assert candidates[0].score > candidates[1].score


def test_discogs_track_count_penalty() -> None:
    album = _Album(
        canonical_artist="Artist One",
        canonical_composer=None,
        canonical_album="Album One",
        year=None,
        tracks=[_Track() for _ in range(10)],
    )
    releases = [
        {
            "id": 1,
            "title": "Album One",
            "artist": "Artist One",
            "year": 2001,
            "track_count": 10,
        },
        {
            "id": 2,
            "title": "Album One",
            "artist": "Artist One",
            "year": 2001,
            "track_count": 3,
        },
    ]
    svc = ReleaseSearchService(musicbrainz=None, discogs=_StubDiscogs(releases))
    candidates = svc._search_discogs_releases(album)
    assert candidates[0].release_id == "1"
    assert candidates[0].score > candidates[1].score
