"""Unit tests for provider fusion de-duplication behavior."""

from __future__ import annotations

from resonance.core.identifier import ProviderRelease, ProviderTrack
from resonance.core.provider_fusion import CombinedProviderClient, NamedProvider


class _StubProvider:
    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = list(releases)

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        _ = fingerprints
        return list(self._releases)

    def search_by_metadata(self, artist: str | None, album: str | None, track_count: int) -> list[ProviderRelease]:
        _ = (artist, album, track_count)
        return list(self._releases)


def test_provider_fusion_dedupes_by_match_keys_without_fingerprints() -> None:
    mb_release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-1",
        title="Album",
        artist="Björk",
        tracks=(
            ProviderTrack(position=1, title="Track One"),
            ProviderTrack(position=2, title="Track Two"),
        ),
    )
    dg_release = ProviderRelease(
        provider="discogs",
        release_id="dg-1",
        title="Album",
        artist="Bjork",
        tracks=(
            ProviderTrack(position=1, title="Track One"),
            ProviderTrack(position=2, title="Track Two"),
        ),
    )

    client = CombinedProviderClient(
        (
            NamedProvider("musicbrainz", _StubProvider([mb_release])),
            NamedProvider("discogs", _StubProvider([dg_release])),
        )
    )

    results = client.search_by_metadata("Björk", "Album", track_count=2)
    assert [entry.release_id for entry in results] == ["mb-1"]


def test_provider_fusion_keeps_distinct_tracklists() -> None:
    mb_release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-1",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track One"),
            ProviderTrack(position=2, title="Track Two"),
        ),
    )
    dg_release = ProviderRelease(
        provider="discogs",
        release_id="dg-1",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Intro"),
            ProviderTrack(position=2, title="Outro"),
        ),
    )

    client = CombinedProviderClient(
        (
            NamedProvider("musicbrainz", _StubProvider([mb_release])),
            NamedProvider("discogs", _StubProvider([dg_release])),
        )
    )

    results = client.search_by_metadata("Artist", "Album", track_count=2)
    assert [entry.release_id for entry in results] == ["mb-1", "dg-1"]
