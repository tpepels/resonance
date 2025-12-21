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

    # Workflow commands
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan library for audio directories",
    )
    scan_parser.add_argument(
        "library_root",
        type=Path,
        help="Library root directory to scan",
    )
    scan_parser.add_argument(
        "--state-db",
        type=Path,
        required=True,
        help="Directory state DB path",
    )
    scan_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )

    resolve_parser = subparsers.add_parser(
        "resolve",
        help="Resolve scanned directories using provider metadata",
    )
    resolve_parser.add_argument(
        "library_root",
        type=Path,
        help="Library root directory to resolve",
    )
    resolve_parser.add_argument(
        "--state-db",
        type=Path,
        required=True,
        help="Directory state DB path",
    )
    resolve_parser.add_argument(
        "--cache-db",
        type=Path,
        help="Provider cache DB path",
    )
    resolve_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )

    prompt_parser = subparsers.add_parser(
        "prompt",
        help="Interactively resolve queued directories",
    )
    prompt_parser.add_argument(
        "--state-db",
        type=Path,
        required=True,
        help="Directory state DB path",
    )
    prompt_parser.add_argument(
        "--cache-db",
        type=Path,
        help="Provider cache DB path",
    )
    prompt_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )

    # Diagnostic commands
    identify_parser = subparsers.add_parser(
        "identify",
        help="Identify a directory and score provider candidates",
    )
    identify_parser.add_argument(
        "directory",
        type=Path,
        help="Directory to identify",
    )
    identify_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )

    plan_parser = subparsers.add_parser(
        "plan",
        help="Create a plan artifact for a resolved directory",
    )
    plan_parser.add_argument(
        "--dir-id",
        required=True,
        help="Directory identifier to plan",
    )
    plan_parser.add_argument(
        "--state-db",
        type=Path,
        help="Directory state DB path",
    )
    plan_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )

    # Prescan command removed - moved to resonance.legacy (V2 code)

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
    apply_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        # Import here to avoid slow startup
        if args.command == "scan":
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.scan import run_scan
            store = DirectoryStateStore(args.state_db)
            try:
                return run_scan(args, store=store)
            finally:
                store.close()
        elif args.command == "resolve":
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.resolve import run_resolve
            store = DirectoryStateStore(args.state_db)
            try:
                return run_resolve(args, store=store)
            finally:
                store.close()
        elif args.command == "prompt":
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.prompt import run_prompt
            store = DirectoryStateStore(args.state_db)
            try:
                return run_prompt(args, store=store)
            finally:
                store.close()
        elif args.command == "identify":
            from .commands.identify import run_identify
            return run_identify(args, provider_client=None)
        elif args.command == "plan":
            if not args.state_db:
                raise ValueError("state_db is required")
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.plan import run_plan
            store = DirectoryStateStore(args.state_db)
            try:
                return run_plan(args, store=store)
            finally:
                store.close()
        # prescan command removed - V2 legacy code in resonance.legacy
        elif args.command == "apply":
            if not args.state_db:
                raise ValueError("state_db is required")
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.apply import run_apply
            store = DirectoryStateStore(args.state_db)
            try:
                return run_apply(args, store=store)
            finally:
                store.close()
        else:
            parser.print_help()
            return 1
    except Exception as exc:  # pragma: no cover - exercised in CLI tests
        from .errors import exit_code_for_exception

        print(str(exc), file=sys.stderr)
        return exit_code_for_exception(exc)


if __name__ == "__main__":
    sys.exit(main())
