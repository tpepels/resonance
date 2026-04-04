"""Command-line interface for Resonance."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _add_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mode",
        choices=["interactive", "automation", "admin"],
        default="interactive",
        help="Invocation profile for policy enforcement",
    )


def _add_json_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )


def _add_state_db_argument(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    parser.add_argument(
        "--state-db",
        type=Path,
        required=required,
        help="Directory state DB path",
    )


def main() -> int:
    """Main CLI entry point."""
    # Load environment variables from .env files
    _load_dotenv_files()

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
    _add_state_db_argument(scan_parser)
    _add_json_argument(scan_parser)
    _add_mode_argument(scan_parser)

    resolve_parser = subparsers.add_parser(
        "resolve",
        help="Resolve scanned directories using provider metadata",
    )
    resolve_parser.add_argument(
        "library_root",
        type=Path,
        help="Library root directory to resolve",
    )
    _add_state_db_argument(resolve_parser)
    resolve_parser.add_argument(
        "--cache-db",
        type=Path,
        help="Provider cache DB path",
    )
    resolve_parser.add_argument(
        "--offline",
        action="store_true",
        help="Run in offline mode (cached responses only)",
    )
    _add_json_argument(resolve_parser)
    resolve_parser.add_argument(
        "--auto-probable",
        action="store_true",
        help="Auto-pin PROBABLE matches when there is a clear winner",
    )
    resolve_parser.add_argument(
        "--auto-probable-min-gap",
        type=float,
        default=0.15,
        help="Minimum score gap for auto-probable (default: 0.15)",
    )
    resolve_parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="In automation/admin mode, return non-zero on warning conditions",
    )
    _add_mode_argument(resolve_parser)

    prompt_parser = subparsers.add_parser(
        "prompt",
        help="Interactively resolve queued directories",
    )
    _add_state_db_argument(prompt_parser)
    prompt_parser.add_argument(
        "--cache-db",
        type=Path,
        help="Provider cache DB path",
    )
    prompt_parser.add_argument(
        "--decisions-file",
        type=Path,
        help="[ADVANCED] JSON file with scripted decisions (non-interactive mode)",
    )
    prompt_parser.add_argument(
        "--record-replay",
        type=Path,
        help="[ADVANCED] Record prompt decisions to replay file (interactive mode)",
    )
    prompt_parser.add_argument(
        "--replay-file",
        type=Path,
        help="[ADVANCED] Replay decisions from recorded replay file",
    )
    _add_json_argument(prompt_parser)
    _add_mode_argument(prompt_parser)

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
    _add_json_argument(identify_parser)
    identify_parser.add_argument(
        "--cache-db",
        type=Path,
        help="Provider cache DB path",
    )
    _add_mode_argument(identify_parser)

    plan_parser = subparsers.add_parser(
        "plan",
        help="Create a plan artifact for a resolved directory",
    )
    plan_parser.add_argument(
        "--dir-id",
        required=True,
        help="Directory identifier to plan",
    )
    _add_state_db_argument(plan_parser, required=False)
    _add_json_argument(plan_parser)
    plan_parser.add_argument(
        "--cache-db",
        type=Path,
        help="Provider cache DB path (required unless pinned release is injected)",
    )
    plan_parser.add_argument(
        "--library-root",
        type=Path,
        help="Library root for provider client bootstrap (required unless pinned release is injected)",
    )
    plan_parser.add_argument(
        "--plan-dir",
        type=Path,
        help="Directory to write plan artifact JSON files into",
    )
    _add_mode_argument(plan_parser)

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
    _add_state_db_argument(apply_parser, required=False)
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
    _add_json_argument(apply_parser)
    apply_parser.add_argument(
        "--tag-patch",
        type=Path,
        dest="tag_patch",
        help="Path to tag patch artifact (optional)",
    )
    apply_parser.add_argument(
        "--no-dry-run",
        action="store_true",
        dest="no_dry_run",
        help="Execute plan for real (default is dry-run safe mode)",
    )
    apply_parser.add_argument(
        "--library-root",
        type=Path,
        dest="library_root",
        help="Library root directory (required when plan uses relative destination paths)",
    )
    _add_mode_argument(apply_parser)

    # Decide command (full pipeline orchestration)
    decide_parser = subparsers.add_parser(
        "decide",
        help="Run full pipeline: scan → resolve → prompt → plan",
    )
    decide_parser.add_argument(
        "library_root",
        type=Path,
        help="Library root directory",
    )
    _add_state_db_argument(decide_parser)
    decide_parser.add_argument(
        "--cache-db",
        type=Path,
        help="Provider cache DB path",
    )
    decide_parser.add_argument(
        "--offline",
        action="store_true",
        help="Run in offline mode (cached responses only)",
    )
    decide_parser.add_argument(
        "--decisions-file",
        type=Path,
        help="[ADVANCED] JSON file with scripted decisions (non-interactive mode)",
    )
    _add_json_argument(decide_parser)
    decide_parser.add_argument(
        "--auto-probable",
        action="store_true",
        help="Auto-pin PROBABLE matches when there is a clear winner",
    )
    decide_parser.add_argument(
        "--auto-probable-min-gap",
        type=float,
        default=0.15,
        help="Minimum score gap for auto-probable (default: 0.15)",
    )
    decide_parser.add_argument(
        "--plan-dir",
        type=Path,
        help="Directory to write plan artifact JSON files into",
    )
    decide_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without user interaction (implies --auto-probable, skips prompt stage)",
    )
    decide_parser.add_argument(
        "--fail-on-prompt",
        action="store_true",
        help="In automation/admin mode, return non-zero if prompt queue remains",
    )
    decide_parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="In automation/admin mode, return non-zero on warning conditions",
    )
    _add_mode_argument(decide_parser)

    app_parser = subparsers.add_parser(
        "app",
        help="Unified interactive entrypoint for all features",
    )
    app_parser.add_argument(
        "library_root",
        type=Path,
        help="Library root directory",
    )
    _add_state_db_argument(app_parser)
    app_parser.add_argument(
        "--cache-db",
        type=Path,
        help="Provider cache DB path",
    )
    app_parser.add_argument(
        "--offline",
        action="store_true",
        help="Run in offline mode (cached responses only)",
    )
    app_parser.add_argument(
        "--plan-dir",
        type=Path,
        help="Directory to write plan artifact JSON files into",
    )
    app_parser.add_argument(
        "--auto-probable",
        action="store_true",
        help="Auto-pin PROBABLE matches when there is a clear winner",
    )
    app_parser.add_argument(
        "--auto-probable-min-gap",
        type=float,
        default=0.15,
        help="Minimum score gap for auto-probable (default: 0.15)",
    )
    _add_json_argument(app_parser)
    audit_parser = subparsers.add_parser(
        "audit",
        help="Inspect a directory's state and audit artifacts",
    )
    audit_parser.add_argument(
        "dir_id",
        help="Directory identifier to audit",
    )
    _add_state_db_argument(audit_parser)
    _add_json_argument(audit_parser)

    # Doctor command
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Validate store invariants and environment sanity",
    )
    _add_state_db_argument(doctor_parser)
    doctor_parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".config" / "resonance" / "settings.json",
        help="Settings path (default: ~/.config/resonance/settings.json)",
    )
    _add_json_argument(doctor_parser)

    # Rollback command
    rollback_parser = subparsers.add_parser(
        "rollback",
        help="Revert applied file operations using an apply report",
    )
    rollback_parser.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Path to apply report artifact",
    )
    _add_state_db_argument(rollback_parser)
    rollback_parser.add_argument(
        "--library-root",
        type=Path,
        required=True,
        dest="library_root",
        help="Library root directory (required for path validation)",
    )
    _add_json_argument(rollback_parser)

    # Unjail command
    unjail_parser = subparsers.add_parser(
        "unjail",
        help="Reset a jailed directory to NEW state",
    )
    unjail_parser.add_argument(
        "dir_id",
        help="Directory identifier to unjail",
    )
    _add_state_db_argument(unjail_parser)
    _add_json_argument(unjail_parser)
    _add_mode_argument(unjail_parser)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        from .api.service import ResonanceService

        service = ResonanceService()
        return service.execute(args)
    except Exception as exc:  # pragma: no cover - exercised in CLI tests
        from .errors import exit_code_for_exception

        print(str(exc), file=sys.stderr)
        return exit_code_for_exception(exc)


def _load_dotenv_files() -> None:
    """Load environment variables from .env files.

    Searches for .env files in the current directory and parent directories,
    loading them in order from most specific to least specific.
    """
    try:
        from dotenv import load_dotenv

        # Load .env files from current directory upwards
        load_dotenv()
    except ImportError:
        # python-dotenv not installed, skip .env loading
        pass


if __name__ == "__main__":
    sys.exit(main())
