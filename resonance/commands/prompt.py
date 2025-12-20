"""Prompt command - answer deferred user prompts."""

from __future__ import annotations

import logging
from argparse import Namespace
from pathlib import Path

from ..app import ResonanceApp
from ..core.models import AlbumInfo
from ..infrastructure.cache import MetadataCache


def run_prompt(args: Namespace) -> int:
    """Run the prompt command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    cache_path = Path(args.cache).expanduser()
    cache = MetadataCache(cache_path)

    deferred = cache.get_deferred_prompts()
    if not deferred:
        print("No deferred prompts found.")
        cache.close()
        return 0

    print(f"Resonance prompt mode ({len(deferred)} pending)")
    print(f"  Cache: {cache_path}")
    print()

    app = ResonanceApp.from_env(
        library_root=Path.cwd(),
        cache_path=cache_path,
        interactive=True,
        dry_run=False,
    )

    try:
        pipeline = app.create_pipeline()
        for directory, _reason in deferred:
            if not directory.exists():
                cache.remove_deferred_prompt(directory)
                continue

            cache.remove_deferred_prompt(directory)
            album = AlbumInfo(directory=directory)
            pipeline.process(album)
    except KeyboardInterrupt:
        print("\nPrompt processing interrupted by user")
        return 130
    finally:
        app.close()
        cache.close()

    return 0
