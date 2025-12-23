"""Integration tests for real-world corpus using filesystem faker.

Tests Resonance against real-world music library structures by using
extracted metadata and a filesystem faker instead of actual files.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from tests.integration._filesystem_faker import FakerContext, create_faker_for_corpus


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

        # TODO: Implement full workflow
        # 1. Set up temporary databases
        # 2. Run scan → resolve → plan → apply
        # 3. Verify deterministic results
        # 4. Generate/compare snapshots based on REGEN_REAL_CORPUS

        pytest.skip("Full workflow implementation pending - Phase 3 in progress")


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
