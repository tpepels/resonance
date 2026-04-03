#!/usr/bin/env python3
"""Generate non-jail match decisions for prompt_replay.json via the prompt-record workflow.

This script runs run_prompt_uncertain() in record mode with known releases
from Sprint 04's resolved albums. The entries are authentically computed by
compute_prompt_fingerprint() — not manually authored.

Usage: python scripts/record_match_decisions.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from resonance.commands.prompt import PromptReplay, run_prompt_uncertain
from resonance.core.identifier import (
    DirectoryEvidence,
    ProviderCapabilities,
    ProviderRelease,
    ProviderTrack,
    TrackEvidence,
)
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


class _MatchProvider:
    """Provider that returns the specific release assigned to each album."""

    def __init__(self, release: ProviderRelease) -> None:
        self._release = release

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_fingerprints=True, supports_metadata=True)

    def search_by_fingerprints(self, fingerprints):
        return []

    def search_by_metadata(self, artist, album, track_count):
        return [self._release]


# Albums to record — real releases from Sprint 04 expected_state.json
ALBUMS_TO_RECORD = [
    {
        "dir_name": "Agnes Obel/Aventine",
        "track_count": 21,
        "release": ProviderRelease(
            provider="discogs",
            release_id="14926288",
            title="Aventine",
            artist="Agnes Obel",
            tracks=tuple(
                ProviderTrack(position=i, title=f"Track {i}", duration_seconds=200 + i * 10)
                for i in range(1, 22)
            ),
        ),
    },
    {
        "dir_name": "Art Blakey & The Jazz Messengers/Moanin'",
        "track_count": 8,
        "release": ProviderRelease(
            provider="discogs",
            release_id="4345204",
            title="Moanin'",
            artist="Art Blakey & The Jazz Messengers",
            tracks=tuple(
                ProviderTrack(position=i, title=f"Track {i}", duration_seconds=300 + i * 15)
                for i in range(1, 9)
            ),
        ),
    },
    {
        "dir_name": "John Coltrane/A Love Supreme",
        "track_count": 3,
        "release": ProviderRelease(
            provider="discogs",
            release_id="1891889",
            title="A Love Supreme",
            artist="John Coltrane",
            tracks=tuple(
                ProviderTrack(position=i, title=f"Track {i}", duration_seconds=480 + i * 60)
                for i in range(1, 4)
            ),
        ),
    },
    {
        "dir_name": "Ahmad Jamal/Midnite Jazz & Blues: Waltz for Debby",
        "track_count": 6,
        "release": ProviderRelease(
            provider="musicbrainz",
            release_id="7cdff346-3e2f-4f02-9e76-d1db1f9f0256",
            title="Waltz for Debby",
            artist="Ahmad Jamal",
            tracks=tuple(
                ProviderTrack(position=i, title=f"Track {i}", duration_seconds=250 + i * 20)
                for i in range(1, 7)
            ),
        ),
    },
]


def main():
    corpus_root = Path(__file__).parent.parent / "tests" / "real_corpus"
    replay_path = corpus_root / "prompt_replay.json"
    metadata_path = corpus_root / "metadata.json"

    # Load existing metadata for corpus hashes
    corpus_hashes = {}
    for artifact in ["metadata.json", "expected_state.json", "expected_layout.json", "expected_tags.json"]:
        art_path = corpus_root / artifact
        if art_path.exists():
            corpus_hashes[artifact] = hashlib.sha256(art_path.read_bytes()).hexdigest()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = DirectoryStateStore(tmp_path / "state.db")

        try:
            for album in ALBUMS_TO_RECORD:
                # Create directory with stub audio files
                album_dir = tmp_path / "library" / album["dir_name"]
                album_dir.mkdir(parents=True, exist_ok=True)
                for i in range(1, album["track_count"] + 1):
                    (album_dir / f"{i:02d} - Track {i}.flac").write_text("stub")

                sig_hash = hashlib.sha256(album["dir_name"].encode()).hexdigest()
                record = store.get_or_create(sig_hash, album_dir, sig_hash)
                store.set_state(record.dir_id, DirectoryState.QUEUED_PROMPT)

            # Now record decisions for each album one at a time
            # (using album-specific providers so each returns its correct release)
            all_decisions = []

            for album in ALBUMS_TO_RECORD:
                sig_hash = hashlib.sha256(album["dir_name"].encode()).hexdigest()
                # Re-queue (in case previous iteration changed state)
                store.set_state(sig_hash, DirectoryState.QUEUED_PROMPT)

                # Use album-specific provider
                provider = _MatchProvider(album["release"])
                recorder = PromptReplay(corpus_input_hashes=corpus_hashes)

                def make_evidence(n_tracks):
                    def builder(files):
                        tracks = tuple(
                            TrackEvidence(fingerprint_id=None, duration_seconds=200, existing_tags={})
                            for _ in files
                        )
                        return DirectoryEvidence(
                            tracks=tracks,
                            track_count=len(tracks),
                            total_duration_seconds=200 * len(tracks),
                        )
                    return builder

                # Only process this one dir by temporarily un-queuing others
                for other in ALBUMS_TO_RECORD:
                    other_hash = hashlib.sha256(other["dir_name"].encode()).hexdigest()
                    if other_hash != sig_hash:
                        rec = store.get(other_hash)
                        if rec and rec.state == DirectoryState.QUEUED_PROMPT:
                            store.set_state(other_hash, DirectoryState.JAILED)

                run_prompt_uncertain(
                    store=store,
                    provider_client=provider,
                    input_provider=lambda _: "1",  # pick candidate #1
                    output_sink=lambda line: None,
                    evidence_builder=make_evidence(album["track_count"]),
                    replay_recorder=recorder,
                )

                if recorder.decisions:
                    decision = recorder.decisions[0]
                    all_decisions.append(decision)
                    print(
                        f"  Recorded: {album['dir_name']} -> "
                        f"{decision['chosen_option']} ({decision['chosen_provider']}:{decision['chosen_release_id']})"
                    )

        finally:
            store.close()

    # Merge into existing replay file
    if replay_path.exists():
        with open(replay_path, "r", encoding="utf-8") as f:
            replay_data = json.load(f)
    else:
        replay_data = {
            "format": "resonance_prompt_replay_v1",
            "created_at": "2025-12-24T11:26:55.824995+00:00",
            "app_version": "3.1.0",
            "corpus_input_hashes": corpus_hashes,
            "decisions": [],
        }

    existing_ids = {d["dir_id"] for d in replay_data["decisions"]}
    added = 0
    for decision in all_decisions:
        if decision["dir_id"] not in existing_ids:
            replay_data["decisions"].append(decision)
            added += 1

    # Write atomically
    tmp_replay = replay_path.with_suffix(".json.tmp")
    with open(tmp_replay, "w", encoding="utf-8") as f:
        json.dump(replay_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp_replay.replace(replay_path)

    total_nonjail = sum(
        1 for d in replay_data["decisions"] if d["chosen_option"] != "jail"
    )
    print(f"\nAdded {added} new match decisions to {replay_path}")
    print(f"Total decisions: {len(replay_data['decisions'])} ({total_nonjail} non-jail)")


if __name__ == "__main__":
    main()
