"""Scan command - process a music directory."""

from __future__ import annotations

import logging
from argparse import Namespace
from pathlib import Path

from ..app import ResonanceApp
from ..core.models import AlbumInfo

logger = logging.getLogger(__name__)


def run_scan(args: Namespace) -> int:
    """Run the scan command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    directory = Path(args.directory).resolve()
    cache_path = Path(args.cache).expanduser()

    print(f"Resonance - Scanning {directory}")
    print(f"Cache: {cache_path}")
    print()

    if args.dry_run:
        print("DRY RUN MODE - No files will be moved\n")

    # Handle unjail
    if args.unjail:
        from ..infrastructure.cache import MetadataCache
        cache = MetadataCache(cache_path)
        count = cache.unjail_directories()
        cache.close()
        print(f"Unjailed {count} directories\n")

    # Create application
    app = ResonanceApp.from_env(
        library_root=directory,
        cache_path=cache_path,
        interactive=True,
        dry_run=args.dry_run,
        delete_nonaudio=args.delete_nonaudio,
    )

    try:
        # Create visitor pipeline
        pipeline = app.create_pipeline()

        # Scan directory
        batch = app.scanner.collect_directory(directory)

        if not batch:
            print(f"No audio files found in {directory}")
            return 0

        print(f"Found {len(batch.files)} audio files\n")

        # Create album
        album = AlbumInfo(directory=batch.directory)

        # Process through pipeline
        print("Processing pipeline:")
        print("  1. Identify (fingerprinting)")
        print("  2. Prompt (user input)")
        print("  3. Enrich (metadata)")
        print("  4. Organize (move files)")
        print("  5. Cleanup (delete empty dirs)")
        print()

        success = pipeline.process(album)

        if success:
            print(f"\n✓ Successfully processed: {directory}")
            if album.destination_path:
                print(f"  → {album.destination_path}")
            return 0
        else:
            print(f"\n✗ Processing stopped early (uncertain or skipped)")
            return 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1

    finally:
        app.close()
