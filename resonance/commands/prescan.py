"""Prescan command - build canonical name mappings."""

from __future__ import annotations

from argparse import Namespace


def run_prescan(args: Namespace) -> int:
    """Run the prescan command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success)
    """
    print(f"Resonance prescan command")
    print(f"  Directory: {args.directory}")
    print(f"  Cache: {args.cache}")
    print()
    print("This is an optional feature not yet implemented.")
    print("It would scan your library to build canonical artist/composer mappings.")
    print("Current core functionality uses on-demand canonicalization instead.")
    return 0
