"""Command-line interface for Resonance."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="resonance",
        description="Clean, focused audio metadata organizer using fingerprinting",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="resonance 0.1.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Scan command
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan and organize a music directory",
    )
    scan_parser.add_argument(
        "directory",
        type=Path,
        help="Directory to scan",
    )
    scan_parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home() / ".cache" / "resonance" / "metadata.db",
        help="Cache database path (default: ~/.cache/resonance/metadata.db)",
    )
    scan_parser.add_argument(
        "--unjail",
        action="store_true",
        help="Reprocess previously skipped directories",
    )
    scan_parser.add_argument(
        "--delete-nonaudio",
        action="store_true",
        help="Delete non-audio files when cleaning up source directories",
    )
    scan_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually moving files",
    )

    # Daemon command
    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Watch directory and process new files in background",
    )
    daemon_parser.add_argument(
        "directory",
        type=Path,
        help="Directory to watch",
    )
    daemon_parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home() / ".cache" / "resonance" / "metadata.db",
        help="Cache database path",
    )
    daemon_parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Polling interval in seconds (default: 10)",
    )
    daemon_parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scan cycle and exit",
    )

    # Prompt command (answer deferred prompts)
    prompt_parser = subparsers.add_parser(
        "prompt",
        help="Answer deferred prompts from daemon mode",
    )
    prompt_parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home() / ".cache" / "resonance" / "metadata.db",
        help="Cache database path",
    )

    # Prescan command (build canonical name mappings)
    prescan_parser = subparsers.add_parser(
        "prescan",
        help="Scan library to build canonical artist/composer mappings",
    )
    prescan_parser.add_argument(
        "directory",
        type=Path,
        help="Library root to scan",
    )
    prescan_parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home() / ".cache" / "resonance" / "metadata.db",
        help="Cache database path",
    )

    # Apply command (execute stored plan)
    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply a stored plan artifact",
    )
    apply_parser.add_argument(
        "--plan",
        type=Path,
        help="Path to plan artifact",
    )
    apply_parser.add_argument(
        "--state-db",
        type=Path,
        help="Directory state DB path",
    )
    apply_parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".config" / "resonance" / "settings.json",
        help="Settings path (default: ~/.config/resonance/settings.json)",
    )
    apply_parser.add_argument(
        "--tag-writer-backend",
        choices=["meta-json", "mutagen"],
        help="Override tag writer backend for this run",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Import here to avoid slow startup
    if args.command == "scan":
        from .commands.scan import run_scan
        return run_scan(args)
    elif args.command == "daemon":
        from .commands.daemon import run_daemon
        return run_daemon(args)
    elif args.command == "prompt":
        from .commands.prompt import run_prompt
        return run_prompt(args)
    elif args.command == "prescan":
        from .commands.prescan import run_prescan
        return run_prescan(args)
    elif args.command == "apply":
        from .commands.apply import run_apply
        return run_apply(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
