"""Integration tests for standalone plan command behavior."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from resonance.commands.plan import run_plan
from resonance.core.identifier import ProviderCapabilities, ProviderRelease, ProviderTrack
from resonance.core.state import DirectoryState
from resonance.errors import ValidationError
from resonance.infrastructure.directory_store import DirectoryStateStore


class _FakeProviderClient:
    """Minimal ProviderClient test double for release_by_id lookups."""

    def __init__(self, release: ProviderRelease | None) -> None:
        self._release = release
        self.calls: list[tuple[str, str]] = []

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_fingerprints=False, supports_metadata=True)

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        return []

    def search_by_metadata(
        self, artist: str | None, album: str | None, track_count: int
    ) -> list[ProviderRelease]:
        return []

    def release_by_id(self, provider: str, release_id: str) -> ProviderRelease | None:
        self.calls.append((provider, release_id))
        return self._release


def _make_release() -> ProviderRelease:
    return ProviderRelease(
        provider="musicbrainz",
        release_id="mb-release-123",
        title="Test Album",
        artist="Test Artist",
        tracks=(
            ProviderTrack(position=1, title="Track A"),
            ProviderTrack(position=2, title="Track B"),
        ),
    )


def _seed_resolved_record(store: DirectoryStateStore, directory: Path) -> None:
    dir_id = "dir-plan-standalone"
    signature_hash = "a" * 64
    store.get_or_create(dir_id, directory, signature_hash)
    store.set_state(
        dir_id,
        DirectoryState.RESOLVED_AUTO,
        pinned_provider="musicbrainz",
        pinned_release_id="mb-release-123",
    )


def test_plan_uses_provider_client_when_pinned_release_not_injected(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _seed_resolved_record(store, source_dir)

    provider = _FakeProviderClient(_make_release())
    args = Namespace(dir_id="dir-plan-standalone", json=False)
    output: list[str] = []

    code = run_plan(args, store=store, provider_client=provider, output_sink=output.append)

    assert code == 0
    assert provider.calls == [("musicbrainz", "mb-release-123")]
    combined = "\n".join(output)
    assert "plan: dir_id=dir-plan-standalone" in combined
    assert "ops=2" in combined

    artifacts = store.get_audit_artifacts("dir-plan-standalone")
    assert artifacts.get("last_plan_hash")
    assert artifacts.get("last_plan_version") == "v1"


def test_plan_requires_provider_client_when_release_not_injected(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _seed_resolved_record(store, source_dir)

    args = Namespace(dir_id="dir-plan-standalone", json=False)

    with pytest.raises(ValidationError, match="provider_client is required"):
        run_plan(args, store=store)


def test_plan_fails_when_provider_cannot_load_pinned_release(tmp_path: Path) -> None:
    store = DirectoryStateStore(tmp_path / "state.db")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    _seed_resolved_record(store, source_dir)

    provider = _FakeProviderClient(release=None)
    args = Namespace(dir_id="dir-plan-standalone", json=False)

    with pytest.raises(ValidationError, match="failed to load pinned release"):
        run_plan(args, store=store, provider_client=provider)
