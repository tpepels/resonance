"""Unit tests for Resolver - the control plane for release resolution.

These tests enforce the critical "no re-matches" invariant and verify
that Resolver correctly bridges DirectoryStateStore and Identifier.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resonance.core.identifier import (
    ConfidenceTier,
    DirectoryEvidence,
    IdentificationResult,
    ProviderRelease,
    ProviderTrack,
    TrackEvidence,
)
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


# -------------------------
# Test stubs / helpers
# -------------------------

class StubProviderClient:
    """Tracks provider calls precisely (for asserting exact call counts)."""

    def __init__(self, releases: list[ProviderRelease]):
        self.releases = list(releases)
        self.search_by_fingerprints_calls = 0
        self.search_by_metadata_calls = 0

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        self.search_by_fingerprints_calls += 1
        return list(self.releases)

    def search_by_metadata(
        self, artist: str | None, album: str | None, track_count: int
    ) -> list[ProviderRelease]:
        self.search_by_metadata_calls += 1
        return []

    @property
    def total_calls(self) -> int:
        return self.search_by_fingerprints_calls + self.search_by_metadata_calls

    def was_called(self) -> bool:
        return self.total_calls > 0

    def assert_not_called(self) -> None:
        assert self.total_calls == 0, (
            f"Provider was called unexpectedly: "
            f"fingerprints={self.search_by_fingerprints_calls}, "
            f"metadata={self.search_by_metadata_calls}"
        )


def _install_identify_guard(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """
    Patch resonance.core.resolver.identify so tests can prove it was (or wasn't) called.

    Returns a dict with a call counter.
    """
    from resonance.core import resolver as resolver_mod

    calls = {"count": 0}

    def fake_identify(*args, **kwargs):
        calls["count"] += 1
        raise AssertionError("identify() must not be called in this scenario")

    monkeypatch.setattr(resolver_mod, "identify", fake_identify)
    return calls


def _install_identify_spy(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """
    Patch resonance.core.resolver.identify to count calls, but still run real identifier
    by delegating to the imported symbol at patch time is not possible (it would recurse).
    Instead, return a minimal result directly.

    Use this when you want to assert identify was invoked.
    """
    from resonance.core import resolver as resolver_mod

    calls = {"count": 0}

    def fake_identify(evidence, provider_client):
        calls["count"] += 1
        # Minimal deterministic result (CERTAIN with best_candidate present) is tricky
        # because best_candidate is derived from candidates; easiest is to return PROBABLE
        # or UNSURE and assert queueing. For CERTAIN-flow, rely on integration of Identifier.
        return IdentificationResult(
            candidates=(),
            tier=ConfidenceTier.UNSURE,
            reasons=("spy-result",),
            evidence=evidence,
        )

    monkeypatch.setattr(resolver_mod, "identify", fake_identify)
    return calls


# -------------------------
# Tests A: No re-matches / pinned reuse (CRITICAL)
# -------------------------

def test_resolved_auto_directory_skips_identify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """RESOLVED_AUTO directories must skip identify() entirely."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
            pinned_confidence=0.95,
        )

        provider = StubProviderClient([])

        # Prove identify() is NOT called
        calls = _install_identify_guard(monkeypatch)

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=DirectoryEvidence(tracks=(), track_count=0, total_duration_seconds=0),
            store=store,
            provider_client=provider,
        )

        assert calls["count"] == 0
        provider.assert_not_called()

        final = store.get("dir-1")
        assert final.state == DirectoryState.RESOLVED_AUTO
        assert final.pinned_release_id == "mb-123"
        assert outcome.state == DirectoryState.RESOLVED_AUTO
        assert outcome.pinned_release_id == "mb-123"
    finally:
        store.close()


def test_resolved_user_directory_skips_identify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """RESOLVED_USER directories must skip identify() entirely."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_USER,
            pinned_provider="discogs",
            pinned_release_id="dg-456",
            pinned_confidence=1.0,
        )

        provider = StubProviderClient([])

        calls = _install_identify_guard(monkeypatch)

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=DirectoryEvidence(tracks=(), track_count=0, total_duration_seconds=0),
            store=store,
            provider_client=provider,
        )

        assert calls["count"] == 0
        provider.assert_not_called()

        final = store.get("dir-1")
        assert final.state == DirectoryState.RESOLVED_USER
        assert final.pinned_release_id == "dg-456"
        assert outcome.state == DirectoryState.RESOLVED_USER
        assert outcome.pinned_release_id == "dg-456"
    finally:
        store.close()


def test_path_change_does_not_trigger_identify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Path change with same signature must not trigger identify()."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/a"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-123",
        )

        provider = StubProviderClient([])

        calls = _install_identify_guard(monkeypatch)

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/b"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=DirectoryEvidence(tracks=(), track_count=0, total_duration_seconds=0),
            store=store,
            provider_client=provider,
        )

        assert calls["count"] == 0
        provider.assert_not_called()

        final = store.get("dir-1")
        assert final.last_seen_path == Path("/music/b")
        assert final.state == DirectoryState.RESOLVED_AUTO
        assert final.pinned_release_id == "mb-123"
        assert outcome.state == DirectoryState.RESOLVED_AUTO
    finally:
        store.close()


def test_signature_change_triggers_identify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Signature change must trigger identify() (at least once)."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id="mb-old",
        )

        updated = store.get_or_create("dir-1", Path("/music/album"), "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        assert updated.state == DirectoryState.NEW
        assert updated.pinned_release_id is None

        provider = StubProviderClient([])

        # Prove identify *is* called by forcing resolver.identify to return UNSURE
        calls = _install_identify_spy(monkeypatch)

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            evidence=DirectoryEvidence(
                tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
                track_count=1,
                total_duration_seconds=180,
            ),
            store=store,
            provider_client=provider,
        )

        assert calls["count"] == 1
        assert outcome.state == DirectoryState.QUEUED_PROMPT
        assert outcome.needs_prompt is True
    finally:
        store.close()


# -------------------------
# Tests B: CERTAIN tier autopin
# -------------------------

def test_certain_tier_autopins_to_resolved_auto(tmp_path: Path):
    """CERTAIN confidence must auto-pin to RESOLVED_AUTO."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Test Album",
            artist="Test Artist",
            tracks=(
                ProviderTrack(position=1, title="Track 1", fingerprint_id="fp1"),
                ProviderTrack(position=2, title="Track 2", fingerprint_id="fp2"),
            ),
        )
        provider = StubProviderClient([release])

        evidence = DirectoryEvidence(
            tracks=(
                TrackEvidence(fingerprint_id="fp1", duration_seconds=180),
                TrackEvidence(fingerprint_id="fp2", duration_seconds=200),
            ),
            track_count=2,
            total_duration_seconds=380,
        )

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=evidence,
            store=store,
            provider_client=provider,
        )

        final = store.get("dir-1")
        assert final.state == DirectoryState.RESOLVED_AUTO
        assert final.pinned_provider == "musicbrainz"
        assert final.pinned_release_id == "mb-123"
        assert final.pinned_confidence is not None

        assert outcome.state == DirectoryState.RESOLVED_AUTO
        assert outcome.pinned_release_id == "mb-123"
        assert outcome.needs_prompt is False
    finally:
        store.close()


def test_certain_autopin_persists_scoring_version_in_outcome(tmp_path: Path):
    """CERTAIN autopin must include scoring_version in outcome for audit."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Album",
            artist="Artist",
            tracks=(ProviderTrack(position=1, title="Track", fingerprint_id="fp1"),),
        )
        provider = StubProviderClient([release])

        evidence = DirectoryEvidence(
            tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
            track_count=1,
            total_duration_seconds=180,
        )

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=evidence,
            store=store,
            provider_client=provider,
        )

        assert outcome.state == DirectoryState.RESOLVED_AUTO
        assert outcome.scoring_version == "v1"
    finally:
        store.close()


def test_certain_does_not_prompt(tmp_path: Path):
    """CERTAIN must not require user prompting."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Album",
            artist="Artist",
            tracks=(ProviderTrack(position=1, title="Track", fingerprint_id="fp1"),),
        )
        provider = StubProviderClient([release])

        evidence = DirectoryEvidence(
            tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
            track_count=1,
            total_duration_seconds=180,
        )

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=evidence,
            store=store,
            provider_client=provider,
        )

        assert outcome.needs_prompt is False

        final = store.get("dir-1")
        assert final.state == DirectoryState.RESOLVED_AUTO
        assert final.state != DirectoryState.QUEUED_PROMPT
    finally:
        store.close()


# -------------------------
# Tests C: Queueing for PROBABLE/UNSURE
# -------------------------

def test_probable_tier_queues_for_prompt(tmp_path: Path):
    """PROBABLE confidence must queue for user resolution."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Album",
            artist="Artist",
            tracks=(
                ProviderTrack(position=1, title="Track 1", fingerprint_id="fp1"),
                ProviderTrack(position=2, title="Track 2"),
            ),
        )
        provider = StubProviderClient([release])

        evidence = DirectoryEvidence(
            tracks=(
                TrackEvidence(fingerprint_id="fp1", duration_seconds=180),
                TrackEvidence(fingerprint_id="fp2", duration_seconds=200),
            ),
            track_count=2,
            total_duration_seconds=380,
        )

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=evidence,
            store=store,
            provider_client=provider,
        )

        final = store.get("dir-1")
        assert final.state == DirectoryState.QUEUED_PROMPT
        assert final.pinned_release_id is None

        assert outcome.state == DirectoryState.QUEUED_PROMPT
        assert outcome.needs_prompt is True
    finally:
        store.close()


def test_unsure_tier_queues_for_prompt(tmp_path: Path):
    """UNSURE confidence must queue for user resolution."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Album",
            artist="Artist",
            tracks=(ProviderTrack(position=1, title="Track 1"),),
        )
        provider = StubProviderClient([release])

        evidence = DirectoryEvidence(
            tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
            track_count=1,
            total_duration_seconds=180,
        )

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=evidence,
            store=store,
            provider_client=provider,
        )

        final = store.get("dir-1")
        assert final.state == DirectoryState.QUEUED_PROMPT

        assert outcome.state == DirectoryState.QUEUED_PROMPT
        assert outcome.needs_prompt is True
    finally:
        store.close()


def test_queued_prompt_not_reprocessed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Already queued directories should not be reprocessed (no identify, no provider)."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

        provider = StubProviderClient([])

        calls = _install_identify_guard(monkeypatch)

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=DirectoryEvidence(
                tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
                track_count=1,
                total_duration_seconds=180,
            ),
            store=store,
            provider_client=provider,
        )

        assert calls["count"] == 0
        provider.assert_not_called()

        final = store.get("dir-1")
        assert final.state == DirectoryState.QUEUED_PROMPT
        assert final.pinned_release_id is None

        assert outcome.state == DirectoryState.QUEUED_PROMPT
        assert outcome.needs_prompt is True
    finally:
        store.close()


# -------------------------
# Tests D: Jail semantics
# -------------------------

def test_jailed_directory_skips_processing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """JAILED directories must be skipped entirely (no identify, no provider)."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(record.dir_id, DirectoryState.JAILED)

        provider = StubProviderClient([])

        calls = _install_identify_guard(monkeypatch)

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=DirectoryEvidence(
                tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
                track_count=1,
                total_duration_seconds=180,
            ),
            store=store,
            provider_client=provider,
        )

        assert calls["count"] == 0
        provider.assert_not_called()

        final = store.get("dir-1")
        assert final.state == DirectoryState.JAILED
        assert outcome.state == DirectoryState.JAILED
    finally:
        store.close()


def test_unjail_resets_to_new(tmp_path: Path):
    """Unjailing must reset state to NEW for reprocessing."""
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        record = store.get_or_create("dir-1", Path("/music/album"), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        store.set_state(record.dir_id, DirectoryState.JAILED)

        # Simulate unjail (state transition)
        store.set_state(record.dir_id, DirectoryState.NEW)

        release = ProviderRelease(
            provider="musicbrainz",
            release_id="mb-123",
            title="Album",
            artist="Artist",
            tracks=(ProviderTrack(position=1, title="Track", fingerprint_id="fp1"),),
        )
        provider = StubProviderClient([release])

        evidence = DirectoryEvidence(
            tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
            track_count=1,
            total_duration_seconds=180,
        )

        from resonance.core.resolver import resolve_directory

        outcome = resolve_directory(
            dir_id="dir-1",
            path=Path("/music/album"),
            signature_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            evidence=evidence,
            store=store,
            provider_client=provider,
        )

        assert provider.was_called()

        final = store.get("dir-1")
        assert final.state != DirectoryState.JAILED
        assert outcome.state in (DirectoryState.RESOLVED_AUTO, DirectoryState.QUEUED_PROMPT)
    finally:
        store.close()
