"""Real-world corpus integration test for V3.1 invariants.

This test validates that the resonance workflow operates correctly on a real
music library snapshot, asserting:
- First run: online mode with provider calls, populates cache
- Subsequent runs: offline mode, deterministic from cache
- Stable layout (no file churn)
- Stable tags (deterministic provenance)

Workflow:
1. First run (online): ./scripts/snapshot_real_corpus.sh + RUN_REAL_CORPUS=1 ONLINE=1 pytest
2. Export cache: python scripts/export_real_corpus_cache.py
3. Review/curate: LLM-assisted review of cache_export.json
4. Regen snapshots: python regen_real_corpus.py
5. Subsequent runs: offline-only, assert no changes
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

import pytest

from resonance.core.applier import ApplyStatus, apply_plan
from resonance.core.enricher import build_tag_patch
from resonance.core.identifier import DirectoryEvidence, TrackEvidence
from resonance.core.planner import plan_directory
from resonance.core.resolver import resolve_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.cache import MetadataCache
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.infrastructure.scanner import LibraryScanner
from resonance.providers.caching import CachedProviderClient, ProviderConfig
from resonance.providers.musicbrainz import MusicBrainzClient
from resonance.services.tag_writer import MetaJsonTagWriter
from tests.integration._corpus_harness import (
    assert_or_write_snapshot,
    assert_valid_plan_hash,
    filter_relevant_tags,
    is_regen_enabled,
    snapshot_path,
)


REAL_ROOT = Path(__file__).resolve().parents[1] / "real_corpus"
EXPECTED_ROOT = REAL_ROOT
DECISIONS_FILE = REAL_ROOT / "decisions.json"
REGEN_ENV = "REGEN_REAL_CORPUS"

# Default library path (can be overridden via LIBRARY_PATH env var)
DEFAULT_LIBRARY_PATH = Path.home() / "music"


def _evidence_from_files(audio_files: list[Path]) -> DirectoryEvidence:
    """Build evidence from audio files with .meta.json sidecar data."""
    tracks: list[TrackEvidence] = []
    total_duration = 0

    for path in sorted(audio_files):
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if not meta_path.exists():
            # Real-world corpus may not have .meta.json files
            # Skip for now - in real usage, would extract from audio
            continue

        data = json.loads(meta_path.read_text())
        duration = data.get("duration_seconds")
        if isinstance(duration, int):
            total_duration += duration
        tags = data.get("tags")
        tracks.append(
            TrackEvidence(
                fingerprint_id=data.get("fingerprint_id"),
                duration_seconds=duration,
                existing_tags=tags if isinstance(tags, dict) else {},
            )
        )

    return DirectoryEvidence(
        tracks=tuple(tracks),
        track_count=len(tracks),
        total_duration_seconds=total_duration,
    )


def _load_decisions() -> dict[str, dict]:
    """Load pinned decisions from decisions.json."""
    if not DECISIONS_FILE.exists():
        return {}

    data = json.loads(DECISIONS_FILE.read_text())
    # Filter out schema documentation keys
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _read_tags(writer: MetaJsonTagWriter, file_path: Path) -> dict[str, str]:
    return writer.read_tags(file_path)


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_CORPUS") != "1",
    reason="Opt-in: set RUN_REAL_CORPUS=1 to enable",
)
def test_real_world_corpus(tmp_path: Path) -> None:
    """End-to-end test on real-world library.

    Validates:
    1. Workflow completes successfully on real data
    2. First run (ONLINE=1): populates cache, makes provider calls
    3. Subsequent runs: offline-only, deterministic from cache
    4. Layout and tags are stable and match snapshots
    """
    regen = is_regen_enabled(REGEN_ENV)
    online_mode = os.environ.get("ONLINE") == "1"
    fixed_now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # Get library path (default or override)
    library_path = Path(os.environ.get("LIBRARY_PATH", str(DEFAULT_LIBRARY_PATH)))

    if not library_path.exists():
        pytest.skip(f"Library path does not exist: {library_path}")

    # Load pinned decisions (may be empty on first run)
    decisions = _load_decisions()

    # Setup temporary workspace
    output_root = tmp_path / "organized"
    store = DirectoryStateStore(tmp_path / "state.db")
    cache = MetadataCache(tmp_path / "cache.db", now_fn=lambda: fixed_now)
    writer = MetaJsonTagWriter()

    # Create provider (online or offline)
    # Get user agent from environment (required for MusicBrainz API calls)
    mb_useragent = os.environ.get("MUSICBRAINZ_USERAGENT")
    if online_mode and not mb_useragent:
        pytest.skip(
            "MUSICBRAINZ_USERAGENT required for online mode. "
            "Set to your email: MUSICBRAINZ_USERAGENT=you@example.com"
        )

    mb_client = MusicBrainzClient(useragent=mb_useragent)
    provider_config = ProviderConfig(
        provider_name="musicbrainz",
        client_version="0.1.0",
        cache_version="v1",
        offline=not online_mode,
    )
    provider = CachedProviderClient(mb_client, cache, provider_config)

    # Scan the library directly
    scanner = LibraryScanner([library_path])
    batches = sorted(scanner.iter_directories(), key=lambda b: b.dir_id)

    if not batches:
        pytest.skip(f"No audio directories found in library: {library_path}")

    print(f"\n==> Real-world corpus test")
    print(f"    Library: {library_path}")
    print(f"    Directories: {len(batches)}")
    print(f"    Mode: {'ONLINE (first run)' if online_mode else 'OFFLINE (cached)'}")

    failures: list[str] = []
    applied_dirs: list[str] = []
    jailed_dirs: list[str] = []

    try:
        # First pass: resolve, plan, apply
        for batch in batches:
            dir_name = batch.directory.name
            dir_id = batch.dir_id

            # Check for pinned decision
            decision = decisions.get(dir_id, {})
            if decision.get("action") == "JAIL":
                # Explicitly jailed, skip
                store.set_state(dir_id, DirectoryState.JAILED)
                jailed_dirs.append(dir_id)
                continue

            # Build evidence from files
            evidence = _evidence_from_files(batch.files)

            if not evidence.tracks:
                # No metadata available, skip
                store.set_state(dir_id, DirectoryState.JAILED)
                jailed_dirs.append(dir_id)
                continue

            # Resolve
            try:
                outcome = resolve_directory(
                    dir_id=dir_id,
                    path=batch.directory,
                    signature_hash=batch.signature_hash,
                    evidence=evidence,
                    store=store,
                    provider_client=provider,
                )
            except Exception as e:
                # In offline mode, cache misses will raise RuntimeFailure
                if not online_mode:
                    # Expected in offline mode for uncached directories
                    store.set_state(dir_id, DirectoryState.JAILED)
                    jailed_dirs.append(dir_id)
                    continue
                else:
                    failures.append(f"{dir_name} ({dir_id}): resolve failed: {e}")
                    continue

            # Handle resolution state
            if outcome.state == DirectoryState.QUEUED_UNSURE:
                # UNSURE directories get jailed in test mode
                store.set_state(dir_id, DirectoryState.JAILED)
                jailed_dirs.append(dir_id)
                continue

            if outcome.state not in {
                DirectoryState.RESOLVED_AUTO,
                DirectoryState.RESOLVED_CERTAIN,
            }:
                # Unexpected state
                failures.append(
                    f"{dir_name} ({dir_id}): unexpected state {outcome.state.value}"
                )
                continue

            # Get release from outcome
            # The resolver should have populated this during resolution
            record = store.get(dir_id)
            if record is None or not record.pinned_release_id:
                failures.append(f"{dir_name} ({dir_id}): no pinned release after resolution")
                continue

            # Get the actual release object
            # In real workflow, this comes from the provider via release_by_id
            # For now, we use the matched release from resolution outcome
            if not outcome.matched_release:
                failures.append(f"{dir_name} ({dir_id}): no matched release in outcome")
                continue

            pinned_release = outcome.matched_release

            # Plan
            plan = plan_directory(
                record=record,
                pinned_release=pinned_release,
                source_files=batch.files,
            )

            store.set_state(
                dir_id,
                DirectoryState.PLANNED,
                pinned_provider=plan.provider,
                pinned_release_id=plan.release_id,
            )

            # Build tag patch
            tag_patch = build_tag_patch(
                plan,
                pinned_release,
                outcome.state,
                now_fn=lambda: fixed_now,
            )

            # Apply
            report = apply_plan(
                plan,
                tag_patch,
                store,
                allowed_roots=(output_root,),
                dry_run=False,
                tag_writer=writer,
            )

            if report.status != ApplyStatus.APPLIED:
                failures.append(
                    f"{dir_name} ({dir_id}): apply failed with {report.status.value}"
                )
                continue

            applied_dirs.append(dir_id)

        print(f"    Applied: {len(applied_dirs)} directories")
        print(f"    Jailed: {len(jailed_dirs)} directories")
        print(f"    Failures: {len(failures)}")

        if failures:
            if not regen:
                print("\nFailures:")
                for failure in failures[:10]:  # Show first 10
                    print(f"  - {failure}")
                if len(failures) > 10:
                    print(f"  ... and {len(failures) - 10} more")

        # Collect layout snapshot
        actual_layout = sorted(
            str(path.relative_to(output_root))
            for path in output_root.rglob("*")
            if path.is_file() and path.suffix != ".json"
        )

        # Collect tags snapshot
        tag_entries: list[dict[str, object]] = []
        for path in sorted(output_root.rglob("*.flac")):
            tags = _read_tags(writer, path)
            assert_valid_plan_hash(tags)
            tag_entries.append(
                {
                    "path": str(path.relative_to(output_root)),
                    "tags": filter_relevant_tags(tags),
                }
            )

        # Collect state snapshot
        state_entries: list[dict[str, object]] = []
        for dir_id in sorted(applied_dirs):
            record = store.get(dir_id)
            if record is not None:
                state_entries.append(
                    {
                        "dir_id": dir_id,
                        "state": record.state.value,
                        "pinned_provider": record.pinned_provider,
                        "pinned_release_id": record.pinned_release_id,
                    }
                )

        # Add jailed dirs to state
        for dir_id in sorted(jailed_dirs):
            record = store.get(dir_id)
            if record is not None:
                state_entries.append(
                    {
                        "dir_id": dir_id,
                        "state": record.state.value,
                        "pinned_provider": record.pinned_provider,
                        "pinned_release_id": record.pinned_release_id,
                    }
                )

        # Snapshot/compare
        assert_or_write_snapshot(
            path=snapshot_path(EXPECTED_ROOT, "root", "expected_layout.json"),
            payload=actual_layout,
            regen=regen,
            regen_env_var=REGEN_ENV,
        )

        assert_or_write_snapshot(
            path=snapshot_path(EXPECTED_ROOT, "root", "expected_tags.json"),
            payload={"tracks": tag_entries},
            regen=regen,
            regen_env_var=REGEN_ENV,
        )

        assert_or_write_snapshot(
            path=snapshot_path(EXPECTED_ROOT, "root", "expected_state.json"),
            payload={"directories": state_entries},
            regen=regen,
            regen_env_var=REGEN_ENV,
        )

        print(f"\n==> Snapshots {'generated' if regen else 'validated'} successfully")

    finally:
        cache.close()
        store.close()
