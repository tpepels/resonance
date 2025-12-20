"""Prescan command - build canonical name mappings."""

from __future__ import annotations

import logging
from argparse import Namespace
from pathlib import Path

from ..core.identity.matching import normalize_token
from ..infrastructure.cache import MetadataCache
from ..infrastructure.scanner import LibraryScanner
from ..services.metadata_reader import MetadataReader


def run_prescan(args: Namespace) -> int:
    """Run the prescan command.

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

    print("Resonance prescan")
    print(f"  Directory: {directory}")
    print(f"  Cache: {cache_path}")
    print()

    scanner = LibraryScanner(roots=[directory])
    cache = MetadataCache(cache_path)

    categories = [
        ("artist", "artist"),
        ("composer", "composer"),
        ("performer", "performer"),
        ("album_artist", "album_artist"),
        ("conductor", "conductor"),
    ]

    added = 0
    scanned = 0

    for batch in scanner.iter_directories():
        for path in batch.files:
            track = MetadataReader.read_track(path)
            scanned += 1

            for category, attr in categories:
                value = getattr(track, attr, None)
                if not value:
                    continue
                token = normalize_token(value)
                if not token:
                    continue
                cache_key = f"{category}::{token}"
                if cache.get_canonical_name(cache_key) is None:
                    cache.set_canonical_name(cache_key, value.strip())
                    added += 1

    cache.close()

    print(f"Scanned {scanned} files, added {added} canonical mappings.")
    return 0
