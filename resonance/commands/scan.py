"""Scan command - process a music directory."""

from __future__ import annotations

import logging
from argparse import Namespace
from pathlib import Path

from ..app import ResonanceApp
from ..core.models import AlbumInfo
from ..infrastructure.scanner import LibraryScanner
from ..commands.output import emit_output as _emit_output

logger = logging.getLogger(__name__)


def _scan_summary(directory: Path) -> dict:
    scanner = LibraryScanner([directory])
    batch = scanner.collect_directory(directory)
    if not batch:
        return {
            "directory": str(directory),
            "status": "NO_AUDIO",
            "audio_count": 0,
            "non_audio_count": 0,
            "dir_id": None,
            "signature_hash": None,
        }
    return {
        "directory": str(directory),
        "status": "FOUND",
        "audio_count": len(batch.files),
        "non_audio_count": len(batch.non_audio_files),
        "dir_id": batch.dir_id,
        "signature_hash": batch.signature_hash,
    }


def run_scan(args: Namespace, *, output_sink=print) -> int:
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

    if getattr(args, "json", False):
        payload = _scan_summary(directory)
        _emit_output(
            command="scan",
            payload=payload,
            json_output=True,
            output_sink=output_sink,
            human_lines=(),
        )
        return 0

    output_sink(f"Resonance - Scanning {directory}")
    output_sink(f"Cache: {cache_path}")
    output_sink("")

    if args.dry_run:
        output_sink("DRY RUN MODE - No files will be moved\n")

    # Handle unjail
    if args.unjail:
        from ..infrastructure.cache import MetadataCache
        cache = MetadataCache(cache_path)
        count = cache.unjail_directories()
        cache.close()
        output_sink(f"Unjailed {count} directories\n")

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
            output_sink(f"No audio files found in {directory}")
            return 0

        output_sink(f"Found {len(batch.files)} audio files\n")

        # Create album
        album = AlbumInfo(directory=batch.directory)

        # Process through pipeline
        output_sink("Processing pipeline:")
        output_sink("  1. Identify (fingerprinting)")
        output_sink("  2. Prompt (user input)")
        output_sink("  3. Enrich (metadata)")
        output_sink("  4. Organize (move files)")
        output_sink("  5. Cleanup (delete empty dirs)")
        output_sink("")

        success = pipeline.process(album)

        if success:
            output_sink(f"\n✓ Successfully processed: {directory}")
            if album.destination_path:
                output_sink(f"  → {album.destination_path}")
            return 0
        else:
            output_sink("\n✗ Processing stopped early (uncertain or skipped)")
            return 1

    except KeyboardInterrupt:
        output_sink("\n\nInterrupted by user")
        return 130

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1

    finally:
        app.close()
