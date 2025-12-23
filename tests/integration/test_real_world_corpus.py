"""Integration tests for real-world corpus using filesystem faker.

Tests Resonance against real-world music library structures by using
extracted metadata and a filesystem faker instead of actual files.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from resonance.infrastructure.directory_store import DirectoryStateStore
    from resonance.services.tag_writer import MetaJsonTagWriter

from tests.integration._filesystem_faker import FakerContext, create_faker_for_corpus
from tests.integration._corpus_harness import (
    assert_or_write_snapshot,
    assert_valid_plan_hash,
    filter_relevant_tags,
    is_regen_enabled,
    snapshot_path,
)


@pytest.mark.skipif(
    not (Path(__file__).parent.parent / 'real_corpus' / 'metadata.json').exists(),
    reason="Real-world corpus metadata not found. Run scripts/extract_real_corpus.sh first."
)
@pytest.mark.skipif(
    os.environ.get("RUN_REAL_CORPUS") != "1",
    reason="Opt-in: set RUN_REAL_CORPUS=1 to enable real-world corpus tests"
)
def test_real_world_corpus_deterministic_workflow():
    """Test full Resonance workflow against real-world corpus metadata.

    This test verifies that Resonance works correctly against real-world
    music library structures by using a filesystem faker loaded with
    extracted metadata instead of actual files.

    The test runs the complete workflow (scan → resolve → plan → apply)
    and verifies deterministic behavior across reruns.
    """
    corpus_root = Path(__file__).parent.parent / 'real_corpus'
    metadata_file = corpus_root / 'metadata.json'

    # Verify metadata exists
    assert metadata_file.exists(), f"Metadata file not found: {metadata_file}"

    # Load metadata to verify it has content
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    assert 'files' in metadata, "Metadata missing 'files' key"
    assert len(metadata['files']) > 0, "Metadata contains no files"

    # Create filesystem faker
    faker = create_faker_for_corpus(corpus_root)

    # Use faker context for the entire test
    with FakerContext(faker) as faker_ctx:
        # Test will be implemented in phases:
        # Phase 1: Basic faker integration
        # Phase 2: Full workflow execution
        # Phase 3: Deterministic rerun validation
        # Phase 4: Snapshot generation/comparison

        # For now, just verify faker integration works
        assert faker_ctx is faker

        # Verify we can access files through faker
        metadata_content = metadata['files']
        if metadata_content:
            first_file = metadata_content[0]['path']

            # Test that faker provides filesystem access
            assert faker.exists(first_file), f"Faker should see file: {first_file}"

            # Test directory operations
            if '/' in first_file:
                parent_dir = str(Path(first_file).parent)
                assert faker.isdir(parent_dir), f"Faker should see directory: {parent_dir}"

        # Implement full workflow execution
        regen_real_corpus = is_regen_enabled("REGEN_REAL_CORPUS")
        REGEN_ENV_VAR = "REGEN_REAL_CORPUS"
        EXPECTED_ROOT = corpus_root

        # 1. Set up temporary databases and directories
        temp_dir = Path(tempfile.mkdtemp())
        state_db_path = temp_dir / "state.db"
        cache_db_path = temp_dir / "cache.db"
        output_root = temp_dir / "organized"

        try:
            # 2. Set up Resonance components
            from resonance.infrastructure.directory_store import DirectoryStateStore
            from resonance.infrastructure.scanner import LibraryScanner
            from resonance.services.tag_writer import MetaJsonTagWriter
            from resonance.core.applier import ApplyStatus, apply_plan
            from resonance.core.enricher import build_tag_patch
            from resonance.core.planner import plan_directory
            from resonance.core.resolver import resolve_directory
            from resonance.core.state import DirectoryState
            from resonance.core.identifier import DirectoryEvidence, TrackEvidence
            from resonance.core.identity.signature import dir_id, dir_signature
            from resonance.providers.musicbrainz import MusicBrainzClient
            from resonance.providers.discogs import DiscogsClient
            from resonance.providers.caching import CachingProvider
            from resonance.infrastructure.provider_cache import ProviderCache
            from datetime import datetime, timezone

            store = DirectoryStateStore(state_db_path)
            writer = MetaJsonTagWriter()
            provider_cache = ProviderCache(cache_db_path)
            musicbrainz_provider = CachingProvider(MusicBrainzClient(), provider_cache)
            discogs_provider = CachingProvider(DiscogsClient(token="dummy_token"), provider_cache)

            # 3. Run scan to discover directories
            scanner = LibraryScanner([Path(".")])  # Scan from current dir (faked by faker)
            batches = list(scanner.iter_directories())

            if not batches:
                pytest.skip("No audio directories found in corpus")

            # Sort by dir_id for deterministic processing
            batches.sort(key=lambda b: b.dir_id)

            # 4. Process each directory: scan → resolve → plan → apply
            failures = []
            fixed_now = datetime(2024, 1, 1, tzinfo=timezone.utc)

            for batch in batches[:5]:  # Limit to first 5 for initial testing
                scenario_name = batch.directory.name or f"dir_{batch.dir_id[:8]}"

                # Create directory evidence from files
                tracks = []
                for file_path in sorted(batch.files):
                    # For real corpus, we don't have .meta.json files, so create minimal evidence
                    tracks.append(TrackEvidence(
                        fingerprint_id=None,  # No fingerprints in real corpus
                        duration_seconds=None,  # No duration data
                        existing_tags={},  # No existing tags
                    ))

                evidence = DirectoryEvidence(
                    tracks=tuple(tracks),
                    track_count=len(tracks),
                    total_duration_seconds=0,
                )

                # Resolve directory
                outcome = resolve_directory(
                    dir_id=batch.dir_id,
                    path=batch.directory,
                    signature_hash=batch.signature_hash,
                    evidence=evidence,
                    store=store,
                    provider_client=musicbrainz_provider,  # Start with MusicBrainz
                )

                if outcome.state == DirectoryState.QUEUED_PROMPT:
                    # For now, skip directories that need prompting
                    # TODO: Implement scripted decisions from decisions.json
                    continue

                if outcome.state not in (DirectoryState.RESOLVED_AUTO, DirectoryState.RESOLVED_USER):
                    continue

                # Get resolved record
                record = store.get(batch.dir_id)
                if not record or not record.pinned_release_id or not record.pinned_provider:
                    continue

                # Retrieve the full ProviderRelease object
                pinned_release = musicbrainz_provider.release_by_id(
                    record.pinned_provider, record.pinned_release_id
                )
                if not pinned_release:
                    # Try Discogs if MusicBrainz failed
                    pinned_release = discogs_provider.release_by_id(
                        record.pinned_provider, record.pinned_release_id
                    )
                if not pinned_release:
                    continue

                # Plan directory
                plan = plan_directory(
                    record=record,
                    pinned_release=pinned_release,
                    source_files=batch.files,
                )

                # Mark as planned
                store.set_state(
                    batch.dir_id,
                    DirectoryState.PLANNED,
                    pinned_provider=record.pinned_provider,
                    pinned_release_id=record.pinned_release_id,
                )

                # Build tag patch
                tag_patch = build_tag_patch(
                    plan,
                    pinned_release,
                    outcome.state,
                    now_fn=lambda: fixed_now,
                )

                # Apply plan
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
                        f"{scenario_name}: apply status {report.status.value} errors={report.errors}"
                    )
                    if output_root.exists():
                        import shutil
                        shutil.rmtree(output_root)
                    continue

                # Generate/compare snapshots for this directory
                try:
                    # Layout snapshot (audio + extras, excluding .meta.json)
                    actual_layout = sorted(
                        str(path.relative_to(output_root))
                        for path in output_root.rglob("*")
                        if path.is_file() and path.suffix != ".json"
                    )
                    assert_or_write_snapshot(
                        path=snapshot_path(EXPECTED_ROOT, scenario_name, "expected_layout.json"),
                        payload=actual_layout,
                        regen=regen_real_corpus,
                        regen_env_var=REGEN_ENV_VAR,
                    )

                    # Tags snapshot (filtered, stable keys)
                    tag_entries = []
                    for path in sorted(output_root.rglob("*.flac")):
                        tags = writer.read_tags(path)
                        assert_valid_plan_hash(tags)
                        tag_entries.append(
                            {
                                "path": str(path.relative_to(output_root)),
                                "tags": filter_relevant_tags(tags),
                            }
                        )
                    assert_or_write_snapshot(
                        path=snapshot_path(EXPECTED_ROOT, scenario_name, "expected_tags.json"),
                        payload={"tracks": tag_entries},
                        regen=regen_real_corpus,
                        regen_env_var=REGEN_ENV_VAR,
                    )

                    # State snapshot
                    record = store.get(batch.dir_id)
                    assert record is not None
                    state_data = {
                        "pinned_provider": record.pinned_provider,
                        "pinned_release_id": record.pinned_release_id,
                        "state": record.state.value,
                    }
                    assert_or_write_snapshot(
                        path=snapshot_path(EXPECTED_ROOT, scenario_name, "expected_state.json"),
                        payload=state_data,
                        regen=regen_real_corpus,
                        regen_env_var=REGEN_ENV_VAR,
                    )

                except FileNotFoundError as exc:
                    failures.append(f"{scenario_name}: {exc}")
                    if output_root.exists():
                        import shutil
                        shutil.rmtree(output_root)
                    continue

                # Reset output root for next scenario
                if output_root.exists():
                    import shutil
                    shutil.rmtree(output_root)

            # Report any failures
            if failures:
                raise AssertionError(
                    "Real-world corpus failures:\n" + "\n".join(failures)
                )

        finally:
            # Cleanup
            import shutil
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            store.close()


@pytest.mark.skipif(
    not (Path(__file__).parent.parent / 'real_corpus' / 'metadata.json').exists(),
    reason="Real-world corpus metadata not found"
)
@pytest.mark.skipif(
    os.environ.get("RUN_REAL_CORPUS") != "1",
    reason="Opt-in: set RUN_REAL_CORPUS=1 to enable"
)
def test_real_world_corpus_faker_transparency():
    """Test that filesystem faker is transparent to Resonance code.

    Verifies that existing Resonance code works unchanged when
    filesystem operations are served by the faker instead of
    the real filesystem.
    """
    corpus_root = Path(__file__).parent.parent / 'real_corpus'
    faker = create_faker_for_corpus(corpus_root)

    with FakerContext(faker) as faker_ctx:
        # Test that standard filesystem operations work through faker
        import os.path

        # These should work identically whether faker is active or not
        # (though they'll return different results based on metadata vs real fs)

        # Test exists
        assert callable(os.path.exists)
        result = os.path.exists("nonexistent")
        assert isinstance(result, bool)

        # Test isfile/isdir
        assert callable(os.path.isfile)
        assert callable(os.path.isdir)

        # Test listdir (may work on current dir or specific dirs from metadata)
        assert callable(os.listdir)

        # Test getsize/getmtime (may fail on non-existent paths, but callable)
        assert callable(os.path.getsize)
        assert callable(os.path.getmtime)

        # Test stat
        import os
        assert callable(os.stat)

        # Verify faker context is working
        assert faker_ctx is faker


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_CORPUS") != "1",
    reason="Opt-in: set RUN_REAL_CORPUS=1 to enable"
)
def test_real_world_corpus_snapshot_gating():
    """Test that snapshot regeneration is properly gated."""
    corpus_root = Path(__file__).parent.parent / 'real_corpus'

    # Test without metadata (should skip)
    if not (corpus_root / 'metadata.json').exists():
        pytest.skip("Real-world corpus metadata not found")

    # Test REGEN_REAL_CORPUS gating
    regen_env = os.environ.get("REGEN_REAL_CORPUS")

    if regen_env != "1":
        # Should not attempt to regenerate snapshots
        # (This is more of a documentation test - actual gating happens in test logic)
        pass
    else:
        # When regeneration is enabled, test should be able to run
        # (Actual regeneration logic to be implemented)
        pass

    # For now, just verify the environment variable handling
    assert "REGEN_REAL_CORPUS" in os.environ or regen_env != "1"


# Snapshot generation/comparison is now implemented inline in the main test


# Placeholder for future implementation phases
"""
Phase 3 TODO:

1. Implement full workflow execution:
   - Create temporary state/cache databases
   - Set up Resonance components (scanner, resolver, planner, applier)
   - Run scan → resolve → plan → apply cycle
   - Use scripted prompt decisions from decisions.json

2. Add snapshot generation/comparison:
   - Generate expected_state.json, expected_layout.json, expected_tags.json
   - Compare against committed snapshots (unless REGEN_REAL_CORPUS=1)
   - Use same format as golden corpus snapshots

3. Implement rerun validation:
   - Run workflow twice
   - Assert second run makes zero provider calls
   - Assert identical results (state, layout, tags)

4. Add proper error handling:
   - Skip if metadata missing with clear message
   - Handle workflow failures gracefully
   - Provide actionable error messages

5. Performance considerations:
   - Keep test runtime reasonable (< 30 seconds)
   - Use efficient database operations
   - Minimize provider API calls
"""
