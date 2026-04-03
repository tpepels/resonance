"""Integration test: replay proof with real match decisions (Sprint 05).

Proves Product Guarantees 4 and 5:
  4 — Replay is deterministic when assumptions match
  5 — Replay fails loudly on mismatch

Test flow:
  1. Record 3 real match decisions (not jail) via prompt-record workflow
  2. Replay the recorded file and confirm all decisions applied (exit 0)
  3. Alter one decision's fingerprint (single hex char flip)
  4. Replay the altered file and confirm hard failure (ValidationError)
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from resonance.commands.prompt import (
    PromptReplay,
    compute_prompt_fingerprint,
    run_prompt_uncertain,
)
from resonance.core.identifier import (
    DirectoryEvidence,
    ProviderCapabilities,
    ProviderRelease,
    ProviderTrack,
    TrackEvidence,
)
from resonance.core.state import DirectoryState
from resonance.errors import ValidationError
from resonance.infrastructure.directory_store import DirectoryStateStore


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _StubProvider:
    """Returns pre-configured releases for every metadata search."""

    def __init__(self, releases: list[ProviderRelease]) -> None:
        self._releases = releases

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_fingerprints=True, supports_metadata=True)

    def search_by_fingerprints(self, fingerprints):
        return []

    def search_by_metadata(self, artist, album, track_count):
        return list(self._releases)


# Three albums with real provider / release-id shapes
_ALBUMS = [
    {
        "dir_id": "replay-proof-abbey-road",
        "name": "The Beatles - Abbey Road",
        "tracks": [
            ("01 - Come Together.flac", 259),
            ("02 - Something.flac", 182),
            ("03 - Maxwells Silver Hammer.flac", 207),
        ],
        "release": ProviderRelease(
            provider="musicbrainz",
            release_id="b1b12e0a-dead-beef-cafe-abcdef012345",
            title="Abbey Road",
            artist="The Beatles",
            tracks=(
                ProviderTrack(position=1, title="Come Together", duration_seconds=259),
                ProviderTrack(position=2, title="Something", duration_seconds=182),
                ProviderTrack(position=3, title="Maxwell's Silver Hammer", duration_seconds=207),
            ),
        ),
    },
    {
        "dir_id": "replay-proof-kind-of-blue",
        "name": "Miles Davis - Kind of Blue",
        "tracks": [
            ("01 - So What.flac", 562),
            ("02 - Freddie Freeloader.flac", 589),
        ],
        "release": ProviderRelease(
            provider="discogs",
            release_id="1308576",
            title="Kind of Blue",
            artist="Miles Davis",
            tracks=(
                ProviderTrack(position=1, title="So What", duration_seconds=562),
                ProviderTrack(position=2, title="Freddie Freeloader", duration_seconds=589),
            ),
        ),
    },
    {
        "dir_id": "replay-proof-ok-computer",
        "name": "Radiohead - OK Computer",
        "tracks": [
            ("01 - Airbag.flac", 286),
            ("02 - Paranoid Android.flac", 383),
            ("03 - Subterranean Homesick Alien.flac", 270),
        ],
        "release": ProviderRelease(
            provider="musicbrainz",
            release_id="c2c0a882-face-b00c-9abc-def012345678",
            title="OK Computer",
            artist="Radiohead",
            tracks=(
                ProviderTrack(position=1, title="Airbag", duration_seconds=286),
                ProviderTrack(position=2, title="Paranoid Android", duration_seconds=383),
                ProviderTrack(position=3, title="Subterranean Homesick Alien", duration_seconds=270),
            ),
        ),
    },
]


def _evidence_for(track_defs: list[tuple[str, int]]) -> DirectoryEvidence:
    """Build DirectoryEvidence from (filename, duration) pairs."""
    tracks = tuple(
        TrackEvidence(fingerprint_id=None, duration_seconds=dur, existing_tags={})
        for _, dur in track_defs
    )
    return DirectoryEvidence(
        tracks=tracks,
        track_count=len(tracks),
        total_duration_seconds=sum(dur for _, dur in track_defs),
    )


def _setup_corpus(tmp_path: Path) -> DirectoryStateStore:
    """Create stub directories and a state store with albums in QUEUED_PROMPT."""
    store = DirectoryStateStore(tmp_path / "state.db")
    for album in _ALBUMS:
        album_dir = tmp_path / "library" / album["name"]
        album_dir.mkdir(parents=True, exist_ok=True)
        for filename, _ in album["tracks"]:
            (album_dir / filename).write_text("stub")
        record = store.get_or_create(album["dir_id"], album_dir, "a" * 64)
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)
    return store


def _requeue_all(store: DirectoryStateStore) -> None:
    """Reset all test albums back to QUEUED_PROMPT for another pass."""
    for album in _ALBUMS:
        store.set_state(album["dir_id"], DirectoryState.QUEUED_PROMPT)


# Evidence builder keyed by directory — returns matching durations
_EVIDENCE_CACHE: dict[str, DirectoryEvidence] = {}
for _album in _ALBUMS:
    _dir_name = _album["name"]
    _EVIDENCE_CACHE[_dir_name] = _evidence_for(_album["tracks"])


def _evidence_builder(audio_files: list[Path]) -> DirectoryEvidence:
    """Return evidence whose durations match the album definition."""
    # Identify album by parent directory name
    parent_name = audio_files[0].parent.name
    if parent_name in _EVIDENCE_CACHE:
        return _EVIDENCE_CACHE[parent_name]
    # Fallback: generic evidence
    tracks = tuple(
        TrackEvidence(fingerprint_id=None, duration_seconds=100, existing_tags={})
        for _ in audio_files
    )
    return DirectoryEvidence(
        tracks=tracks,
        track_count=len(tracks),
        total_duration_seconds=100 * len(tracks),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_replay_proof_record_replay_and_altered_failure(tmp_path: Path) -> None:
    """Full record → replay → altered-fingerprint-failure cycle."""
    all_releases = [album["release"] for album in _ALBUMS]
    provider = _StubProvider(all_releases)
    store = _setup_corpus(tmp_path)

    try:
        # ── STEP 1: Record 3 match decisions ──────────────────────────
        replay_recorder = PromptReplay(corpus_input_hashes={"test": "hash"})
        record_output: list[str] = []

        run_prompt_uncertain(
            store=store,
            provider_client=provider,
            input_provider=lambda _prompt: "1",   # always pick candidate #1
            output_sink=record_output.append,
            evidence_builder=_evidence_builder,
            replay_recorder=replay_recorder,
        )

        # All three must be non-jail match decisions
        assert len(replay_recorder.decisions) == 3, (
            f"Expected 3 recorded decisions, got {len(replay_recorder.decisions)}"
        )
        for decision in replay_recorder.decisions:
            assert decision["chosen_option"].startswith("choice_"), (
                f"Expected choice_N, got {decision['chosen_option']}"
            )
            assert decision["chosen_provider"] is not None
            assert decision["chosen_release_id"] is not None

        # All three dirs should now be RESOLVED_USER
        for album in _ALBUMS:
            rec = store.get(album["dir_id"])
            assert rec is not None
            assert rec.state == DirectoryState.RESOLVED_USER, (
                f"{album['dir_id']} should be RESOLVED_USER after recording, got {rec.state}"
            )

        # ── STEP 2: Replay — must succeed ────────────────────────────
        _requeue_all(store)
        replay_data = PromptReplay.from_dict(replay_recorder.to_dict())
        replay_output: list[str] = []

        run_prompt_uncertain(
            store=store,
            provider_client=provider,
            input_provider=lambda _: "",
            output_sink=replay_output.append,
            evidence_builder=_evidence_builder,
            replay_data=replay_data,
        )

        # Verify each replay line appeared and all dirs are RESOLVED_USER
        replay_lines = "\n".join(replay_output)
        assert "REPLAY:" in replay_lines

        for album in _ALBUMS:
            rec = store.get(album["dir_id"])
            assert rec is not None
            assert rec.state == DirectoryState.RESOLVED_USER, (
                f"{album['dir_id']} should be RESOLVED_USER after replay, got {rec.state}"
            )

        # ── STEP 3: Altered fingerprint → hard failure ───────────────
        _requeue_all(store)
        altered_dict = copy.deepcopy(replay_recorder.to_dict())
        original_fp = altered_dict["decisions"][0]["prompt_fingerprint"]
        flipped = "0" if original_fp[0] != "0" else "1"
        altered_dict["decisions"][0]["prompt_fingerprint"] = flipped + original_fp[1:]
        altered_replay = PromptReplay.from_dict(altered_dict)

        with pytest.raises(ValidationError, match="fingerprint mismatch"):
            run_prompt_uncertain(
                store=store,
                provider_client=provider,
                input_provider=lambda _: "",
                output_sink=lambda _: None,
                evidence_builder=_evidence_builder,
                replay_data=altered_replay,
            )

    finally:
        store.close()


def test_replay_failure_exit_code_is_nonzero() -> None:
    """ValidationError from replay mismatch carries exit_code 2."""
    assert ValidationError.exit_code == 2


def test_replay_jail_decisions_applied(tmp_path: Path) -> None:
    """Jail decisions are also faithfully replayed (not silently skipped)."""
    release = ProviderRelease(
        provider="musicbrainz",
        release_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        title="Test Album",
        artist="Test Artist",
        tracks=(ProviderTrack(position=1, title="Track 1", duration_seconds=180),),
    )
    provider = _StubProvider([release])

    store = DirectoryStateStore(tmp_path / "state.db")
    try:
        album_dir = tmp_path / "library" / "jail-test"
        album_dir.mkdir(parents=True, exist_ok=True)
        (album_dir / "01 - Track.flac").write_text("stub")
        record = store.get_or_create("jail-test-dir", album_dir, "b" * 64)
        store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

        # Record a jail decision
        recorder = PromptReplay(corpus_input_hashes={"test": "hash"})
        run_prompt_uncertain(
            store=store,
            provider_client=provider,
            input_provider=lambda _: "s",
            output_sink=lambda _: None,
            evidence_builder=lambda files: DirectoryEvidence(
                tracks=(TrackEvidence(fingerprint_id=None, duration_seconds=180, existing_tags={}),),
                track_count=1,
                total_duration_seconds=180,
            ),
            replay_recorder=recorder,
        )
        assert recorder.decisions[0]["chosen_option"] == "jail"
        assert store.get("jail-test-dir").state == DirectoryState.JAILED

        # Re-queue and replay — dir must become JAILED again
        store.set_state("jail-test-dir", DirectoryState.QUEUED_PROMPT)
        replay = PromptReplay.from_dict(recorder.to_dict())
        run_prompt_uncertain(
            store=store,
            provider_client=provider,
            input_provider=lambda _: "",
            output_sink=lambda _: None,
            evidence_builder=lambda files: DirectoryEvidence(
                tracks=(TrackEvidence(fingerprint_id=None, duration_seconds=180, existing_tags={}),),
                track_count=1,
                total_duration_seconds=180,
            ),
            replay_data=replay,
        )
        assert store.get("jail-test-dir").state == DirectoryState.JAILED

    finally:
        store.close()
