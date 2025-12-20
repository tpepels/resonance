from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from resonance.core.identity.canonicalizer import IdentityCanonicalizer
from resonance.core.models import AlbumInfo, TrackInfo, UserSkippedError
from resonance.core.visitor import VisitorPipeline
from resonance.visitors.identify import IdentifyVisitor
from resonance.visitors.prompt import PromptVisitor


@dataclass
class FakeCache:
    skipped: set[Path]
    releases: dict[Path, tuple[str, str, float]]
    deferred: dict[Path, str]

    def is_directory_skipped(self, directory: Path) -> bool:
        return directory in self.skipped

    def get_directory_release(self, directory: Path):
        return self.releases.get(directory)

    def set_directory_release(
        self, directory: Path, provider: str, release_id: str, confidence: float = 0.0
    ) -> None:
        self.releases[directory] = (provider, release_id, confidence)

    def add_deferred_prompt(self, directory: Path, reason: str) -> None:
        self.deferred[directory] = reason

    def add_skipped_directory(self, directory: Path, reason: str = "user_skipped") -> None:
        self.skipped.add(directory)


@dataclass
class FakeCanonicalCache:
    def get_canonical_name(self, key: str) -> str | None:
        return None

    def set_canonical_name(self, key: str, canonical: str) -> None:
        return None


def make_album(tmp_path: Path) -> AlbumInfo:
    directory = tmp_path / "src_album"
    directory.mkdir()
    track_path = directory / "01 - Track.flac"
    track_path.write_bytes(b"fake-audio")
    return AlbumInfo(directory=directory)


def make_album_with_tracks(tmp_path: Path, names: list[str]) -> AlbumInfo:
    directory = tmp_path / "src_album"
    directory.mkdir()
    for name in names:
        (directory / name).write_bytes(b"fake-audio")
    return AlbumInfo(directory=directory)


def test_pipeline_stops_when_visitor_returns_false(tmp_path: Path):
    album = make_album(tmp_path)

    class StopVisitor:
        def visit(self, _album):
            return False

    class ExplodeVisitor:
        def visit(self, _album):
            raise AssertionError("Must not be called if previous visitor stopped")

    pipeline = VisitorPipeline([StopVisitor(), ExplodeVisitor()])
    assert pipeline.process(album) is False


def test_identify_visitor_handles_missing_release_search(tmp_path: Path, monkeypatch):
    album = make_album(tmp_path)

    def fake_read_track(path: Path) -> TrackInfo:
        return TrackInfo(path=path, artist="Daft Punk", album="Discovery", title="Track")

    monkeypatch.setattr(
        "resonance.services.metadata_reader.MetadataReader.read_track",
        fake_read_track,
    )

    cache = FakeCache(skipped=set(), releases={}, deferred={})
    canonicalizer = IdentityCanonicalizer(cache=FakeCanonicalCache())
    musicbrainz = MagicMock()
    musicbrainz.enrich.return_value = None

    visitor = IdentifyVisitor(
        musicbrainz=musicbrainz,
        canonicalizer=canonicalizer,
        cache=cache,
        release_search=None,
    )

    assert visitor.visit(album) is True
    assert album.canonical_artist == "Daft Punk"
    assert album.canonical_album == "Discovery"
    assert album.is_uncertain is False


def test_identify_visitor_marks_skipped_when_cached(tmp_path: Path):
    album = make_album(tmp_path)
    cache = FakeCache(skipped={album.directory}, releases={}, deferred={})
    canonicalizer = IdentityCanonicalizer(cache=FakeCanonicalCache())
    musicbrainz = MagicMock()
    musicbrainz.enrich.return_value = None

    visitor = IdentifyVisitor(
        musicbrainz=musicbrainz,
        canonicalizer=canonicalizer,
        cache=cache,
        release_search=None,
    )

    assert visitor.visit(album) is False
    assert album.is_skipped is True


def test_identify_visitor_sets_total_tracks_and_canonical_artist(tmp_path: Path, monkeypatch):
    album = make_album_with_tracks(
        tmp_path,
        ["01 - A.flac", "02 - B.flac", "03 - C.flac"],
    )

    def fake_read_track(path: Path) -> TrackInfo:
        if path.name == "03 - C.flac":
            return TrackInfo(path=path, artist="Artist B", album="Album X")
        return TrackInfo(path=path, artist="Artist A", album="Album X")

    monkeypatch.setattr(
        "resonance.services.metadata_reader.MetadataReader.read_track",
        fake_read_track,
    )

    cache = FakeCache(skipped=set(), releases={}, deferred={})
    canonicalizer = IdentityCanonicalizer(cache=FakeCanonicalCache())
    musicbrainz = MagicMock()
    musicbrainz.enrich.return_value = None

    visitor = IdentifyVisitor(
        musicbrainz=musicbrainz,
        canonicalizer=canonicalizer,
        cache=cache,
        release_search=None,
    )

    assert visitor.visit(album) is True
    assert album.total_tracks == 3
    assert album.canonical_artist == "Artist A"
    assert album.canonical_album == "Album X"


def test_identify_visitor_marks_uncertain_without_release_candidates(tmp_path: Path, monkeypatch):
    album = make_album_with_tracks(tmp_path, ["01 - A.flac", "02 - B.flac"])

    def fake_read_track(path: Path) -> TrackInfo:
        return TrackInfo(path=path, artist="Artist A", album="Album X")

    monkeypatch.setattr(
        "resonance.services.metadata_reader.MetadataReader.read_track",
        fake_read_track,
    )

    cache = FakeCache(skipped=set(), releases={}, deferred={})
    canonicalizer = IdentityCanonicalizer(cache=FakeCanonicalCache())
    musicbrainz = MagicMock()
    musicbrainz.enrich.return_value = None
    release_search = MagicMock()
    release_search.search_releases.return_value = []

    visitor = IdentifyVisitor(
        musicbrainz=musicbrainz,
        canonicalizer=canonicalizer,
        cache=cache,
        release_search=release_search,
    )

    assert visitor.visit(album) is True
    assert album.is_uncertain is True


def test_prompt_visitor_jails_directory(tmp_path: Path):
    album = make_album(tmp_path)
    album.is_uncertain = True

    class FakePromptService:
        interactive = True

        def prompt_for_release(self, _album):
            raise UserSkippedError("User chose to skip")

    cache = FakeCache(skipped=set(), releases={}, deferred={})
    visitor = PromptVisitor(prompt_service=FakePromptService(), cache=cache)

    assert visitor.visit(album) is False
    assert album.is_skipped is True
    assert album.directory in cache.skipped


def test_prompt_visitor_defers_when_noninteractive(tmp_path: Path):
    album = make_album(tmp_path)
    album.is_uncertain = True

    class FakePromptService:
        interactive = False

        def prompt_for_release(self, _album):
            raise AssertionError("Should not prompt in non-interactive mode")

    cache = FakeCache(skipped=set(), releases={}, deferred={})
    visitor = PromptVisitor(prompt_service=FakePromptService(), cache=cache)

    assert visitor.visit(album) is False
    assert cache.deferred.get(album.directory) == "uncertain_match"
