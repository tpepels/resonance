"""Integration tests for multi-provider fusion behavior."""

from __future__ import annotations

from pathlib import Path

from resonance.core.identifier import DirectoryEvidence, ProviderCapabilities, ProviderRelease, ProviderTrack, TrackEvidence
from resonance.core.provider_fusion import CombinedProviderClient, NamedProvider
from resonance.core.resolver import resolve_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


class _StubProvider:
    def __init__(self, releases: list[ProviderRelease], *, fail: bool = False) -> None:
        self._releases = list(releases)
        self._fail = fail

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_fingerprints=True,
            supports_metadata=True,
        )

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        if self._fail:
            raise RuntimeError("provider down")
        releases: list[ProviderRelease] = []
        for release in self._releases:
            if any(
                track.fingerprint_id in fingerprints
                for track in release.tracks
                if track.fingerprint_id
            ):
                releases.append(release)
        return releases

    def search_by_metadata(self, artist: str | None, album: str | None, track_count: int) -> list[ProviderRelease]:
        if self._fail:
            raise RuntimeError("provider down")
        return []


def _evidence() -> DirectoryEvidence:
    return DirectoryEvidence(
        tracks=(
            TrackEvidence(fingerprint_id="fp-1", duration_seconds=180),
            TrackEvidence(fingerprint_id="fp-2", duration_seconds=181),
        ),
        track_count=2,
        total_duration_seconds=361,
    )


def test_provider_fusion_agreement_auto_resolves(tmp_path: Path) -> None:
    mb_release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-1",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1", fingerprint_id="fp-1"),
            ProviderTrack(position=2, title="Track 2", fingerprint_id="fp-2"),
        ),
    )
    dg_release = ProviderRelease(
        provider="discogs",
        release_id="dg-1",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1", fingerprint_id="fp-1"),
            ProviderTrack(position=2, title="Track 2", fingerprint_id="fp-2"),
        ),
    )

    client = CombinedProviderClient(
        (
            NamedProvider("musicbrainz", _StubProvider([mb_release])),
            NamedProvider("discogs", _StubProvider([dg_release])),
        )
    )

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        outcome = resolve_directory(
            dir_id="dir-fusion-1",
            path=tmp_path,
            signature_hash="a" * 64,
            evidence=_evidence(),
            store=store,
            provider_client=client,
        )
        assert outcome.state == DirectoryState.RESOLVED_AUTO
        assert outcome.pinned_provider == "musicbrainz"
        assert any(reason.startswith("providers=musicbrainz") for reason in outcome.reasons)
    finally:
        store.close()


def test_provider_fusion_disagree_queues_prompt(tmp_path: Path) -> None:
    mb_release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-1",
        title="Album A",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1", fingerprint_id="fp-1"),
            ProviderTrack(position=2, title="Track 2", fingerprint_id="fp-2"),
        ),
    )
    dg_release = ProviderRelease(
        provider="discogs",
        release_id="dg-1",
        title="Album B",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track X", fingerprint_id="fp-1"),
            ProviderTrack(position=2, title="Track Y", fingerprint_id="fp-2"),
        ),
    )

    client = CombinedProviderClient(
        (
            NamedProvider("musicbrainz", _StubProvider([mb_release])),
            NamedProvider("discogs", _StubProvider([dg_release])),
        )
    )

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        outcome = resolve_directory(
            dir_id="dir-fusion-2",
            path=tmp_path,
            signature_hash="b" * 64,
            evidence=_evidence(),
            store=store,
            provider_client=client,
        )
        assert outcome.state == DirectoryState.QUEUED_PROMPT
        assert outcome.needs_prompt is True
        assert any(reason.startswith("providers=discogs,musicbrainz") for reason in outcome.reasons)
    finally:
        store.close()


def test_provider_fusion_one_provider_down(tmp_path: Path) -> None:
    mb_release = ProviderRelease(
        provider="musicbrainz",
        release_id="mb-1",
        title="Album",
        artist="Artist",
        tracks=(
            ProviderTrack(position=1, title="Track 1", fingerprint_id="fp-1"),
            ProviderTrack(position=2, title="Track 2", fingerprint_id="fp-2"),
        ),
    )

    client = CombinedProviderClient(
        (
            NamedProvider("musicbrainz", _StubProvider([mb_release])),
            NamedProvider("discogs", _StubProvider([], fail=True)),
        )
    )

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        outcome = resolve_directory(
            dir_id="dir-fusion-3",
            path=tmp_path,
            signature_hash="c" * 64,
            evidence=_evidence(),
            store=store,
            provider_client=client,
        )
        assert outcome.state == DirectoryState.RESOLVED_AUTO
        assert outcome.pinned_provider == "musicbrainz"
        assert any(reason.startswith("providers=musicbrainz") for reason in outcome.reasons)
    finally:
        store.close()
