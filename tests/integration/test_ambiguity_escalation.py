"""Test that ambiguous evidence correctly escalates to QUEUED_PROMPT (G3).

Guarantee G3: Ambiguity is a first-class outcome. When two releases score
similarly, the system must escalate to user review rather than guessing.
"""

from __future__ import annotations

from pathlib import Path

from resonance.core.identifier import (
    DirectoryEvidence,
    ProviderCapabilities,
    ProviderRelease,
    ProviderTrack,
    TrackEvidence,
)
from resonance.core.resolver import resolve_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


class _AmbiguousProvider:
    """Provider that returns two releases with near-identical scores."""

    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = releases

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_fingerprints=True, supports_metadata=False)

    def search_by_fingerprints(self, fingerprints: list[str]) -> list[ProviderRelease]:
        return list(self._releases)

    def search_by_metadata(
        self, artist: str | None, album: str | None, track_count: int
    ) -> list[ProviderRelease]:
        return []


def _make_competing_releases() -> list[ProviderRelease]:
    """Two releases with identical track structure — forces ambiguity."""
    return [
        ProviderRelease(
            provider="musicbrainz",
            release_id="mb-release-A",
            title="Original Pressing",
            artist="Shared Artist",
            tracks=(
                ProviderTrack(position=1, title="Track 1", duration_seconds=200,
                              fingerprint_id="fp-1"),
                ProviderTrack(position=2, title="Track 2", duration_seconds=210,
                              fingerprint_id="fp-2"),
                ProviderTrack(position=3, title="Track 3", duration_seconds=195,
                              fingerprint_id="fp-3"),
            ),
        ),
        ProviderRelease(
            provider="musicbrainz",
            release_id="mb-release-B",
            title="Remaster Edition",
            artist="Shared Artist",
            tracks=(
                ProviderTrack(position=1, title="Track 1", duration_seconds=200,
                              fingerprint_id="fp-1"),
                ProviderTrack(position=2, title="Track 2", duration_seconds=210,
                              fingerprint_id="fp-2"),
                ProviderTrack(position=3, title="Track 3", duration_seconds=195,
                              fingerprint_id="fp-3"),
            ),
        ),
    ]


def test_ambiguous_releases_escalate_to_queued_prompt(tmp_path: Path) -> None:
    """Two releases with identical fingerprints and durations → QUEUED_PROMPT.

    This directly proves G3: the system treats ambiguity as a meaningful
    result rather than silently picking one release.
    """
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        evidence = DirectoryEvidence(
            track_count=3,
            tracks=(
                TrackEvidence(
                    duration_seconds=200,
                    fingerprint_id="fp-1",
                    existing_tags={},
                ),
                TrackEvidence(
                    duration_seconds=210,
                    fingerprint_id="fp-2",
                    existing_tags={},
                ),
                TrackEvidence(
                    duration_seconds=195,
                    fingerprint_id="fp-3",
                    existing_tags={},
                ),
            ),
            total_duration_seconds=605,
        )

        releases = _make_competing_releases()
        provider = _AmbiguousProvider(releases)

        outcome = resolve_directory(
            dir_id="ambiguous-dir-001",
            path=tmp_path / "ambiguous_album",
            signature_hash="b" * 64,
            evidence=evidence,
            store=store,
            provider_client=provider,
        )

        # G3: ambiguity escalates to user review, not silent pick
        assert outcome.state == DirectoryState.QUEUED_PROMPT, (
            f"Expected QUEUED_PROMPT for ambiguous evidence, got {outcome.state}. "
            f"Reasons: {outcome.reasons}"
        )
        assert outcome.needs_prompt is True

        # Verify the reason mentions multiple releases
        reasons_text = " ".join(outcome.reasons)
        assert "similar scores" in reasons_text.lower() or "multiple" in reasons_text.lower(), (
            f"Reason should explain ambiguity: {outcome.reasons}"
        )
    finally:
        store.close()


def test_no_candidates_escalates_to_queued_prompt(tmp_path: Path) -> None:
    """Zero provider results → QUEUED_PROMPT, not a silent failure.

    G3: the system surfaces the gap rather than inventing authority.
    """
    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        evidence = DirectoryEvidence(
            track_count=2,
            tracks=(
                TrackEvidence(
                    duration_seconds=180,
                    fingerprint_id=None,
                    existing_tags={},
                ),
                TrackEvidence(
                    duration_seconds=200,
                    fingerprint_id=None,
                    existing_tags={},
                ),
            ),
            total_duration_seconds=380,
        )

        # Provider returns nothing
        provider = _AmbiguousProvider([])

        outcome = resolve_directory(
            dir_id="unknown-dir-001",
            path=tmp_path / "unknown_album",
            signature_hash="c" * 64,
            evidence=evidence,
            store=store,
            provider_client=provider,
        )

        assert outcome.state == DirectoryState.QUEUED_PROMPT
        assert outcome.needs_prompt is True
    finally:
        store.close()
