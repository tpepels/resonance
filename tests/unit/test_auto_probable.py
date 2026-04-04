"""Unit tests for auto-probable resolution (Sprint 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from resonance.core.identifier import (
    ConfidenceTier,
    DirectoryEvidence,
    IdentificationResult,
    ProviderRelease,
    ProviderTrack,
    ReleaseScore,
    TrackEvidence,
)
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


def _make_release(provider: str, release_id: str) -> ProviderRelease:
    return ProviderRelease(
        provider=provider,
        release_id=release_id,
        title="Album",
        artist="Artist",
        tracks=(ProviderTrack(position=1, title="T1", fingerprint_id="fp1"),),
    )


def _make_score(release: ProviderRelease, total_score: float) -> ReleaseScore:
    return ReleaseScore(
        release=release,
        fingerprint_coverage=0.5,
        track_count_match=True,
        duration_fit=0.8,
        year_penalty=0.0,
        total_score=total_score,
    )


def _install_probable_spy(monkeypatch, candidates, gap_scenario="clear"):
    """Patch identify to return PROBABLE with specified candidates."""
    from resonance.core import resolver as resolver_mod

    evidence = DirectoryEvidence(
        tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
        track_count=1,
        total_duration_seconds=180,
    )

    def fake_identify(ev, pc, **kw):
        return IdentificationResult(
            candidates=tuple(candidates),
            tier=ConfidenceTier.PROBABLE,
            reasons=("Probable match: score=0.75",),
            evidence=ev,
        )

    monkeypatch.setattr(resolver_mod, "identify", fake_identify)


def _install_unsure_spy(monkeypatch, candidates):
    """Patch identify to return UNSURE."""
    from resonance.core import resolver as resolver_mod

    def fake_identify(ev, pc, **kw):
        return IdentificationResult(
            candidates=tuple(candidates),
            tier=ConfidenceTier.UNSURE,
            reasons=("Low confidence",),
            evidence=ev,
        )

    monkeypatch.setattr(resolver_mod, "identify", fake_identify)


class TestAutoProblableDisabledByDefault:
    def test_probable_queues_without_flag(self, tmp_path: Path, monkeypatch) -> None:
        """PROBABLE must still queue for prompt when auto_probable is False (default)."""
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            store.get_or_create("dir-1", Path("/music/a"), "a" * 64)
            release = _make_release("musicbrainz", "mb-1")
            score = _make_score(release, 0.75)
            _install_probable_spy(monkeypatch, [score])

            from resonance.core.resolver import resolve_directory

            outcome = resolve_directory(
                dir_id="dir-1",
                path=Path("/music/a"),
                signature_hash="a" * 64,
                evidence=DirectoryEvidence(
                    tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
                    track_count=1,
                    total_duration_seconds=180,
                ),
                store=store,
                provider_client=object(),
            )
            assert outcome.state == DirectoryState.QUEUED_PROMPT
            assert outcome.needs_prompt is True
        finally:
            store.close()


class TestAutoProbableClearWinner:
    def test_single_candidate_auto_pins(self, tmp_path: Path, monkeypatch) -> None:
        """PROBABLE with one candidate and auto_probable=True -> RESOLVED_AUTO."""
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            store.get_or_create("dir-1", Path("/music/a"), "a" * 64)
            release = _make_release("musicbrainz", "mb-1")
            score = _make_score(release, 0.75)
            _install_probable_spy(monkeypatch, [score])

            from resonance.core.resolver import resolve_directory

            outcome = resolve_directory(
                dir_id="dir-1",
                path=Path("/music/a"),
                signature_hash="a" * 64,
                evidence=DirectoryEvidence(
                    tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
                    track_count=1,
                    total_duration_seconds=180,
                ),
                store=store,
                provider_client=object(),
                auto_probable=True,
            )
            assert outcome.state == DirectoryState.RESOLVED_AUTO
            assert outcome.pinned_release_id == "mb-1"
            assert outcome.needs_prompt is False
            assert any("Auto-probable" in r for r in outcome.reasons)
        finally:
            store.close()

    def test_two_candidates_large_gap_auto_pins(self, tmp_path: Path, monkeypatch) -> None:
        """Two candidates with gap >= min_gap -> auto-pin best."""
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            store.get_or_create("dir-1", Path("/music/a"), "a" * 64)
            r1 = _make_release("musicbrainz", "mb-1")
            r2 = _make_release("discogs", "dg-1")
            s1 = _make_score(r1, 0.80)
            s2 = _make_score(r2, 0.60)
            _install_probable_spy(monkeypatch, [s1, s2])

            from resonance.core.resolver import resolve_directory

            outcome = resolve_directory(
                dir_id="dir-1",
                path=Path("/music/a"),
                signature_hash="a" * 64,
                evidence=DirectoryEvidence(
                    tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
                    track_count=1,
                    total_duration_seconds=180,
                ),
                store=store,
                provider_client=object(),
                auto_probable=True,
                auto_probable_min_gap=0.15,
            )
            assert outcome.state == DirectoryState.RESOLVED_AUTO
            assert outcome.pinned_release_id == "mb-1"
        finally:
            store.close()


class TestAutoProbableTightRace:
    def test_two_candidates_small_gap_queues(self, tmp_path: Path, monkeypatch) -> None:
        """Two candidates with gap < min_gap -> queue for prompt."""
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            store.get_or_create("dir-1", Path("/music/a"), "a" * 64)
            r1 = _make_release("musicbrainz", "mb-1")
            r2 = _make_release("discogs", "dg-1")
            s1 = _make_score(r1, 0.75)
            s2 = _make_score(r2, 0.70)
            _install_probable_spy(monkeypatch, [s1, s2])

            from resonance.core.resolver import resolve_directory

            outcome = resolve_directory(
                dir_id="dir-1",
                path=Path("/music/a"),
                signature_hash="a" * 64,
                evidence=DirectoryEvidence(
                    tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
                    track_count=1,
                    total_duration_seconds=180,
                ),
                store=store,
                provider_client=object(),
                auto_probable=True,
                auto_probable_min_gap=0.15,
            )
            assert outcome.state == DirectoryState.QUEUED_PROMPT
            assert outcome.needs_prompt is True
        finally:
            store.close()


class TestAutoProbableUnsure:
    def test_unsure_always_queues(self, tmp_path: Path, monkeypatch) -> None:
        """UNSURE must always queue even with auto_probable=True."""
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            store.get_or_create("dir-1", Path("/music/a"), "a" * 64)
            release = _make_release("musicbrainz", "mb-1")
            score = _make_score(release, 0.50)
            _install_unsure_spy(monkeypatch, [score])

            from resonance.core.resolver import resolve_directory

            outcome = resolve_directory(
                dir_id="dir-1",
                path=Path("/music/a"),
                signature_hash="a" * 64,
                evidence=DirectoryEvidence(
                    tracks=(TrackEvidence(fingerprint_id="fp1", duration_seconds=180),),
                    track_count=1,
                    total_duration_seconds=180,
                ),
                store=store,
                provider_client=object(),
                auto_probable=True,
            )
            assert outcome.state == DirectoryState.QUEUED_PROMPT
            assert outcome.needs_prompt is True
        finally:
            store.close()
