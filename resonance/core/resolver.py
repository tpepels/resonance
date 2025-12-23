"""Resolver - control plane for release resolution.

This module bridges DirectoryStateStore, Identifier, and user interaction.
It enforces the "no re-matches" invariant by checking pinned state before
calling providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from resonance.core.identifier import (
    ConfidenceTier,
    DirectoryEvidence,
    ProviderClient,
    identify,
)
from resonance.core.state import DirectoryRecord, DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


@dataclass(frozen=True)
class ResolveOutcome:
    """Result of attempting to resolve a directory."""

    dir_id: str
    state: DirectoryState
    pinned_provider: Optional[str] = None
    pinned_release_id: Optional[str] = None
    pinned_confidence: Optional[float] = None
    scoring_version: Optional[str] = None
    reasons: tuple[str, ...] = ()
    needs_prompt: bool = False


def resolve_directory(
    dir_id: str,
    path: Path,
    signature_hash: str,
    evidence: DirectoryEvidence,
    store: DirectoryStateStore,
    provider_client: ProviderClient,
) -> ResolveOutcome:
    """Resolve a single directory, respecting pinned decisions.

    Critical invariants:
    - RESOLVED_* directories skip identify() entirely
    - Path changes do not trigger re-identification
    - Signature changes reset state to NEW (handled by store)
    - CERTAIN tier auto-pins to RESOLVED_AUTO
    - PROBABLE/UNSURE queue for user resolution

    Args:
        dir_id: Directory identifier
        path: Current filesystem path
        signature_hash: Current signature
        evidence: Extracted evidence for identification
        store: Directory state store
        provider_client: Provider search interface

    Returns:
        ResolveOutcome describing what happened
    """
    # Get or create record (this handles signature invalidation)
    record = store.get_or_create(dir_id, path, signature_hash)

    # CRITICAL: Skip identify() if already resolved or applied
    if record.state in (
        DirectoryState.RESOLVED_AUTO,
        DirectoryState.RESOLVED_USER,
        DirectoryState.APPLIED,
    ):
        return ResolveOutcome(
            dir_id=record.dir_id,
            state=record.state,
            pinned_provider=record.pinned_provider,
            pinned_release_id=record.pinned_release_id,
            pinned_confidence=record.pinned_confidence,
            reasons=("Already resolved - reusing pinned decision",),
        )

    # Skip if jailed
    if record.state == DirectoryState.JAILED:
        return ResolveOutcome(
            dir_id=record.dir_id,
            state=DirectoryState.JAILED,
            reasons=("Directory is jailed",),
        )

    # Skip if already queued
    if record.state == DirectoryState.QUEUED_PROMPT:
        return ResolveOutcome(
            dir_id=record.dir_id,
            state=DirectoryState.QUEUED_PROMPT,
            needs_prompt=True,
            reasons=("Directory already queued for user resolution",),
        )

    mb_release_id = _musicbrainz_release_from_tags(evidence)
    if mb_release_id:
        updated = store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider="musicbrainz",
            pinned_release_id=mb_release_id,
            pinned_confidence=1.0,
        )
        return ResolveOutcome(
            dir_id=updated.dir_id,
            state=updated.state,
            pinned_provider=updated.pinned_provider,
            pinned_release_id=updated.pinned_release_id,
            pinned_confidence=updated.pinned_confidence,
            reasons=("musicbrainz_albumid present in tags",),
        )

    # State must be NEW - run identification
    result = identify(evidence, provider_client)

    # Handle based on confidence tier
    if result.tier == ConfidenceTier.CERTAIN:
        # Auto-pin to RESOLVED_AUTO
        best = result.best_candidate
        if not best:
            # No candidates despite CERTAIN tier - should not happen with correct scoring
            return _queue_for_prompt(record, store, result.reasons)

        updated = store.set_state(
            record.dir_id,
            DirectoryState.RESOLVED_AUTO,
            pinned_provider=best.release.provider,
            pinned_release_id=best.release.release_id,
            pinned_confidence=best.total_score,
        )

        return ResolveOutcome(
            dir_id=updated.dir_id,
            state=updated.state,
            pinned_provider=updated.pinned_provider,
            pinned_release_id=updated.pinned_release_id,
            pinned_confidence=updated.pinned_confidence,
            scoring_version=result.scoring_version,
            reasons=result.reasons,
        )

    elif result.tier in (ConfidenceTier.PROBABLE, ConfidenceTier.UNSURE):
        # Queue for user resolution
        return _queue_for_prompt(record, store, result.reasons)

    else:
        # Unknown tier - should not happen
        return _queue_for_prompt(record, store, ("Unknown confidence tier",))


def _queue_for_prompt(
    record: DirectoryRecord,
    store: DirectoryStateStore,
    reasons: tuple[str, ...],
) -> ResolveOutcome:
    """Queue a directory for user prompting."""
    # Only transition to QUEUED_PROMPT if not already there
    if record.state != DirectoryState.QUEUED_PROMPT:
        updated = store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)
    else:
        updated = record

    return ResolveOutcome(
        dir_id=updated.dir_id,
        state=DirectoryState.QUEUED_PROMPT,
        needs_prompt=True,
        reasons=reasons,
    )


def _musicbrainz_release_from_tags(evidence: DirectoryEvidence) -> Optional[str]:
    """Return MusicBrainz album id if all tagged tracks agree."""
    release_ids = {
        track.existing_tags.get("musicbrainz_albumid")
        for track in evidence.tracks
        if track.existing_tags.get("musicbrainz_albumid")
    }
    if len(release_ids) == 1:
        return next(iter(release_ids))
    return None
