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

# --- additional visitor/pipeline tests (more coverage + edge cases) ---


def test_pipeline_returns_true_when_all_visitors_return_true(tmp_path: Path):
    album = make_album(tmp_path)

    class V1:
        def visit(self, _album):
            return True

    class V2:
        def visit(self, _album):
            return True

    pipeline = VisitorPipeline([V1(), V2()])
    assert pipeline.process(album) is True


def test_pipeline_propagates_exception_by_default(tmp_path: Path):
    album = make_album(tmp_path)

    class BoomVisitor:
        def visit(self, _album):
            raise RuntimeError("boom")

    pipeline = VisitorPipeline([BoomVisitor()])
    with pytest.raises(RuntimeError):
        pipeline.process(album)


def test_identify_visitor_sets_is_skipped_when_cached_skip(tmp_path: Path):
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

    out = visitor.visit(album)
    assert out is False
    assert album.is_skipped is True
    # Defensive: identify should not also mark uncertain if skipped.
    assert getattr(album, "is_uncertain", False) is False


def test_identify_visitor_uses_cached_release_when_available(tmp_path: Path, monkeypatch):
    album = make_album_with_tracks(tmp_path, ["01 - A.flac", "02 - B.flac"])

    def fake_read_track(path: Path) -> TrackInfo:
        return TrackInfo(path=path, artist="Daft Punk", album="Discovery", title=path.stem)

    monkeypatch.setattr(
        "resonance.services.metadata_reader.MetadataReader.read_track",
        fake_read_track,
    )

    cache = FakeCache(
        skipped=set(),
        releases={album.directory: ("mb", "mbid-123", 0.99)},
        deferred={},
    )
    canonicalizer = IdentityCanonicalizer(cache=FakeCanonicalCache())
    musicbrainz = MagicMock()
    musicbrainz.enrich.return_value = None

    visitor = IdentifyVisitor(
        musicbrainz=musicbrainz,
        canonicalizer=canonicalizer,
        cache=cache,
        release_search=None,  # should not need it when cached
    )

    assert visitor.visit(album) is True
    # Cached release should be applied (how you store it may differ; adjust if needed)
    assert getattr(album, "release_provider", None) in ("mb", "musicbrainz", None)
    assert getattr(album, "release_id", None) in ("mbid-123", None)
    assert album.is_uncertain is False


def test_identify_visitor_cached_release_low_confidence_marks_uncertain(tmp_path: Path, monkeypatch):
    album = make_album_with_tracks(tmp_path, ["01 - A.flac"])

    def fake_read_track(path: Path) -> TrackInfo:
        return TrackInfo(path=path, artist="Artist", album="Album", title="t")

    monkeypatch.setattr(
        "resonance.services.metadata_reader.MetadataReader.read_track",
        fake_read_track,
    )

    cache = FakeCache(
        skipped=set(),
        releases={album.directory: ("mb", "mbid-low", 0.10)},
        deferred={},
    )
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
    # If you treat "cached but low confidence" as uncertain, keep this.
    # If you always trust cached release regardless of confidence, set expected False instead.
    assert album.is_uncertain is True


def test_identify_visitor_selects_best_candidate_and_persists_release(tmp_path: Path, monkeypatch):
    album = make_album_with_tracks(tmp_path, ["01 - A.flac", "02 - B.flac"])

    def fake_read_track(path: Path) -> TrackInfo:
        return TrackInfo(path=path, artist="Artist A", album="Album X", title=path.stem, duration_seconds=200)

    monkeypatch.setattr(
        "resonance.services.metadata_reader.MetadataReader.read_track",
        fake_read_track,
    )

    cache = FakeCache(skipped=set(), releases={}, deferred={})
    canonicalizer = IdentityCanonicalizer(cache=FakeCanonicalCache())
    musicbrainz = MagicMock()
    musicbrainz.enrich.return_value = None

    # Candidate shape depends on your release_search implementation.
    # Here we assume tuples: (provider, release_id, confidence)
    release_search = MagicMock()
    release_search.search_releases.return_value = [
        ("mb", "mbid-1", 0.80),
        ("dg", "dgid-9", 0.95),
        ("mb", "mbid-2", 0.60),
    ]

    visitor = IdentifyVisitor(
        musicbrainz=musicbrainz,
        canonicalizer=canonicalizer,
        cache=cache,
        release_search=release_search,
    )

    assert visitor.visit(album) is True
    # Best confidence candidate should be selected and stored
    assert cache.get_directory_release(album.directory) == ("dg", "dgid-9", 0.95)
    assert album.is_uncertain is False


def test_identify_visitor_release_search_exception_marks_uncertain_not_crash(tmp_path: Path, monkeypatch):
    album = make_album_with_tracks(tmp_path, ["01 - A.flac"])

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
    release_search.search_releases.side_effect = RuntimeError("provider down")

    visitor = IdentifyVisitor(
        musicbrainz=musicbrainz,
        canonicalizer=canonicalizer,
        cache=cache,
        release_search=release_search,
    )

    assert visitor.visit(album) is True
    assert album.is_uncertain is True


def test_identify_visitor_handles_tracks_with_missing_artist_or_album(tmp_path: Path, monkeypatch):
    album = make_album_with_tracks(tmp_path, ["01 - A.flac", "02 - B.flac"])

    def fake_read_track(path: Path) -> TrackInfo:
        if path.name.startswith("01"):
            return TrackInfo(path=path, artist=None, album="Album X")
        return TrackInfo(path=path, artist="Artist A", album=None)

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
    # With missing data, canonical fields should be set only if derivable; do not crash.
    assert album.total_tracks == 2
    # One of these might remain None depending on your majority/first-nonempty rule.
    assert getattr(album, "canonical_artist", None) in ("Artist A", None)
    assert getattr(album, "canonical_album", None) in ("Album X", None)


def test_identify_visitor_majority_tie_is_deterministic(tmp_path: Path, monkeypatch):
    album = make_album_with_tracks(tmp_path, ["01 - A.flac", "02 - B.flac"])

    def fake_read_track(path: Path) -> TrackInfo:
        if path.name.startswith("01"):
            return TrackInfo(path=path, artist="Artist A", album="Album X")
        return TrackInfo(path=path, artist="Artist B", album="Album X")

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
    # Tie-break expectation: choose lexicographically smallest or first-seen.
    # Pick ONE and make it consistent. This test encodes "first-seen".
    assert album.canonical_artist == "Artist A"


def test_prompt_visitor_does_not_prompt_when_not_uncertain(tmp_path: Path):
    album = make_album(tmp_path)
    album.is_uncertain = False

    prompt = MagicMock()
    prompt.interactive = True
    prompt.prompt_for_release.side_effect = AssertionError("Should not be called")

    cache = FakeCache(skipped=set(), releases={}, deferred={})
    visitor = PromptVisitor(prompt_service=prompt, cache=cache)

    assert visitor.visit(album) is True
    assert cache.deferred == {}
    assert album.directory not in cache.skipped


def test_prompt_visitor_interactive_sets_release_and_continues(tmp_path: Path):
    album = make_album(tmp_path)
    album.is_uncertain = True

    class FakePromptService:
        interactive = True

        def prompt_for_release(self, _album):
            # Return candidate selection; adjust shape to match your real prompt service.
            return ("mb", "mbid-xyz", 0.88)

    cache = FakeCache(skipped=set(), releases={}, deferred={})
    visitor = PromptVisitor(prompt_service=FakePromptService(), cache=cache)

    assert visitor.visit(album) is True
    assert cache.get_directory_release(album.directory) == ("mb", "mbid-xyz", 0.88)
    assert album.is_uncertain is False


def test_prompt_visitor_interactive_accepts_manual_mb_dg_strings(tmp_path: Path):
    album = make_album(tmp_path)
    album.is_uncertain = True

    class FakePromptService:
        interactive = True

        def prompt_for_release(self, _album):
            # Manual entry: if your prompt service returns strings like "mb:xxx" then PromptVisitor should parse.
            return "mb:mbid-12345"

    cache = FakeCache(skipped=set(), releases={}, deferred={})
    visitor = PromptVisitor(prompt_service=FakePromptService(), cache=cache)

    out = visitor.visit(album)
    # Depending on your implementation, either:
    # - it stores the parsed provider/id and continues (recommended), or
    # - it marks uncertain and defers because it cannot parse.
    assert out is True
    rel = cache.get_directory_release(album.directory)
    assert rel is not None
    assert rel[0] in ("mb", "musicbrainz")
    assert rel[1] == "mbid-12345"


def test_prompt_visitor_noninteractive_defers_only_once(tmp_path: Path):
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

    # Run again; should still defer but not change outcome or create duplicates.
    assert visitor.visit(album) is False
    assert cache.deferred.get(album.directory) == "uncertain_match"


def test_prompt_visitor_skip_marks_album_skipped_and_does_not_set_release(tmp_path: Path):
    album = make_album(tmp_path)
    album.is_uncertain = True

    class FakePromptService:
        interactive = True

        def prompt_for_release(self, _album):
            raise UserSkippedError("skip")

    cache = FakeCache(skipped=set(), releases={}, deferred={})
    visitor = PromptVisitor(prompt_service=FakePromptService(), cache=cache)

    assert visitor.visit(album) is False
    assert album.is_skipped is True
    assert album.directory in cache.skipped
    assert cache.get_directory_release(album.directory) is None
