#!/usr/bin/env python3
"""Run the full Resonance corpus decision workflow in REAL REPLAY mode.

This script runs the REAL workflow with live providers and replays decisions
from a previously recorded interactive session.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Add the project root to Python path so we can import tests
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.integration._filesystem_faker import FakerContext, create_faker_for_corpus


def main():
    """Run the REAL REPLAY corpus decision workflow."""
    corpus_root = Path(__file__).parent.parent / 'tests' / 'real_corpus'
    metadata_file = corpus_root / 'metadata.json'
    replay_file = corpus_root / 'prompt_replay.json'

    if not metadata_file.exists():
        raise SystemExit(f"ERROR: {metadata_file} not found. Run 'make corpus-extract' first.")

    if not replay_file.exists():
        raise SystemExit(f"ERROR: {replay_file} not found. Run 'make corpus-decide-real-interactive' first.")

    # Check for required credentials
    acoustid_key = os.environ.get('ACOUSTID_API_KEY')
    discogs_token = os.environ.get('DISCOGS_TOKEN')

    if not acoustid_key:
        raise SystemExit("ERROR: ACOUSTID_API_KEY environment variable required for real workflow")

    if not discogs_token:
        raise SystemExit("ERROR: DISCOGS_TOKEN environment variable required for real workflow")

    # Load metadata to verify it has content
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    if not metadata.get('files'):
        raise SystemExit("ERROR: Metadata contains no files")

    # Set up temporary directories
    temp_dir = Path(tempfile.mkdtemp())
    fake_library_root = temp_dir / "fake_library"
    state_db_path = temp_dir / "state.db"
    cache_db_path = temp_dir / "cache.db"

    try:
        # Create fake filesystem from metadata
        print("==> Setting up fake filesystem...")
        faker = create_faker_for_corpus(corpus_root)

        with FakerContext(faker):
            # Create directory structure from metadata
            for file_info in metadata['files']:
                file_path = file_info['path']
                full_path = fake_library_root / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                if not full_path.exists():
                    full_path.touch()

            # 1. Scan directories
            print("==> Scanning directories...")
            from resonance.infrastructure.directory_store import DirectoryStateStore
            from resonance.commands.scan import run_scan
            from argparse import Namespace

            store = DirectoryStateStore(state_db_path)
            try:
                args = Namespace(library_root=fake_library_root, state_db=state_db_path)
                run_scan(args, store=store)
            finally:
                store.close()

            # 2. Resolve directories (REAL mode - network calls)
            print("==> Resolving directories with REAL provider APIs...")
            store = DirectoryStateStore(state_db_path)
            try:
                from resonance.commands.resolve import run_resolve
                args = Namespace(
                    library_root=fake_library_root,
                    state_db=state_db_path,
                    cache_db=cache_db_path,
                    offline=False,  # REAL mode - make network calls
                    json=False
                )
                run_resolve(args, store=store)
            finally:
                store.close()

            # 3. Replay prompt decisions
            print("==> Replaying prompt decisions...")
            store = DirectoryStateStore(state_db_path)
            try:
                from resonance.commands.prompt import run_prompt_replay
                args = Namespace(
                    state_db=state_db_path,
                    cache_db=cache_db_path,
                    replay_file=replay_file
                )
                run_prompt_replay(args, store=store)
            finally:
                store.close()

            # Report provider usage statistics
            print("==> Provider Usage Statistics:")
            from resonance.providers.caching import PROVIDER_CALL_COUNTS
            for provider, stats in PROVIDER_CALL_COUNTS.items():
                http_calls = stats["http_calls"]
                cache_hits = stats["cache_hits"]
                total_calls = http_calls + cache_hits
                if total_calls > 0:
                    print(f"  {provider}: {http_calls} HTTP calls, {cache_hits} cache hits")

    finally:
        # Cleanup
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main()
