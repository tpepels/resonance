"""Daemon command - watch and process directories in background."""

from __future__ import annotations

import logging
import time
from argparse import Namespace
from pathlib import Path

from ..app import ResonanceApp
from ..core.models import AlbumInfo
from ..core.resolver import resolve_directory
from ..infrastructure.cache import MetadataCache

def run_daemon(args: Namespace) -> int:
    """Run the daemon command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    directory = Path(args.directory).resolve()
    cache_path = Path(args.cache).expanduser()

    print("Resonance daemon mode")
    print(f"  Directory: {directory}")
    print(f"  Cache: {cache_path}")
    print(f"  Interval: {args.interval:.1f}s")
    if args.once:
        print("  Mode: one-shot")
    print()

    app = ResonanceApp.from_env(
        library_root=directory,
        cache_path=cache_path,
        interactive=False,
        dry_run=False,
    )

    try:
        while True:
            _process_cycle(app, cache_path)
            if args.once:
                break
            time.sleep(max(args.interval, 1.0))
    except KeyboardInterrupt:
        print("\nDaemon stopped by user")
    finally:
        app.close()

    return 0


def _process_cycle(app: ResonanceApp, cache_path: Path) -> None:
    cache = MetadataCache(cache_path)
    deferred = {path for path, _ in cache.get_deferred_prompts()}
    pipeline = app.create_pipeline()

    for batch in app.scanner.iter_directories():
        if cache.is_directory_skipped(batch.directory):
            continue
        if cache.get_directory_release(batch.directory):
            continue
        if batch.directory in deferred:
            continue

        album = AlbumInfo(directory=batch.directory)
        pipeline.process(album)

    cache.close()


def run_daemon_once(
    *,
    scanner,
    store,
    provider_client,
    evidence_builder,
) -> list:
    """Run a single daemon pass using injected dependencies (testable)."""
    batches = sorted(
        list(scanner.iter_directories()),
        key=lambda batch: (batch.dir_id, str(batch.directory)),
    )
    outcomes = []
    for batch in batches:
        evidence = evidence_builder(batch.files)
        outcome = resolve_directory(
            dir_id=batch.dir_id,
            path=batch.directory,
            signature_hash=batch.signature_hash,
            evidence=evidence,
            store=store,
            provider_client=provider_client,
        )
        outcomes.append(outcome)
    return outcomes
