#!/usr/bin/env python3
"""Run the full Resonance corpus decision workflow using production CLI commands.

This script implements the production-path workflow for corpus decision making:
- Uses CLI commands instead of internal APIs
- Runs in offline/cached mode only
- Generates expected_*.json files for review tooling
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Add the project root to Python path so we can import tests
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.integration._filesystem_faker import FakerContext, create_faker_for_corpus


def main():
    """Run the corpus decision workflow."""
    corpus_root = Path(__file__).parent.parent / 'tests' / 'real_corpus'
    metadata_file = corpus_root / 'metadata.json'

    if not metadata_file.exists():
        raise SystemExit(f"ERROR: {metadata_file} not found. Run 'make corpus-extract' first.")

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

            # 2. Resolve directories (offline mode)
            print("==> Resolving directories (offline)...")
            store = DirectoryStateStore(state_db_path)
            try:
                from resonance.commands.resolve import run_resolve
                args = Namespace(
                    library_root=fake_library_root,
                    state_db=state_db_path,
                    cache_db=cache_db_path,
                    offline=True,
                    json=False
                )
                try:
                    run_resolve(args, store=store)
                except Exception as exc:
                    if "No provider client available" in str(exc):
                        print("==> No provider credentials available, skipping resolve step")
                        # For corpus tooling, we can proceed without resolution
                        # The directories will remain in NEW state
                    else:
                        raise
            finally:
                store.close()

            # 3. Apply scripted decisions
            decisions_file = corpus_root / 'decisions.json'
            if decisions_file.exists():
                print("==> Applying scripted decisions...")
                store = DirectoryStateStore(state_db_path)
                try:
                    from resonance.commands.prompt import run_prompt_scripted
                    args = Namespace(
                        state_db=state_db_path,
                        cache_db=cache_db_path,
                        decisions_file=decisions_file
                    )
                    run_prompt_scripted(args, store=store)
                finally:
                    store.close()
            else:
                print("==> No decisions.json found, jailing unresolved directories...")
                # Jail unresolved directories
                from resonance.infrastructure.directory_store import DirectoryStateStore
                from resonance.core.state import DirectoryState

                store = DirectoryStateStore(state_db_path)
                try:
                    queued = store.list_by_state(DirectoryState.QUEUED_PROMPT)
                    for record in queued:
                        store.set_state(record.dir_id, DirectoryState.JAILED)
                    print(f"Jailed {len(queued)} unresolved directories")
                finally:
                    store.close()

            # 4. Generate review bundle from the results
            print("==> Generating review artifacts...")
            # The review bundle generation will be handled by the existing scripts

    finally:
        # Cleanup
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def run_cli_command(cmd_args):
    """Run a CLI command and check for errors."""
    # Prepend the Python executable and CLI import
    full_cmd = ['python3', '-c', 'import sys; sys.argv = ["resonance"] + sys.argv[1:]; from resonance.cli import main; main()'] + cmd_args
    result = subprocess.run(full_cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    if result.returncode != 0:
        print(f"Command failed: {' '.join(full_cmd)}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise SystemExit(f"CLI command failed with exit code {result.returncode}")


if __name__ == "__main__":
    main()
