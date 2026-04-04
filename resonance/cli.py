"""Command-line interface for Resonance."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


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
        "--offline",
        action="store_true",
        help="Run in offline mode (cached responses only)",
    )
    resolve_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )
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
    identify_parser.add_argument(
        "--cache-db",
        type=Path,
        help="Provider cache DB path",
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
    decide_parser.add_argument(
        "--state-db",
        type=Path,
        required=True,
        help="Directory state DB path",
    )
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
    decide_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )
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
    audit_parser = subparsers.add_parser(
        "audit",
        help="Inspect a directory's state and audit artifacts",
    )
    audit_parser.add_argument(
        "dir_id",
        help="Directory identifier to audit",
    )
    audit_parser.add_argument(
        "--state-db",
        type=Path,
        required=True,
        help="Directory state DB path",
    )
    audit_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )

    # Doctor command
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Validate store invariants and environment sanity",
    )
    doctor_parser.add_argument(
        "--state-db",
        type=Path,
        required=True,
        help="Directory state DB path",
    )
    doctor_parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".config" / "resonance" / "settings.json",
        help="Settings path (default: ~/.config/resonance/settings.json)",
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )

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
    rollback_parser.add_argument(
        "--state-db",
        type=Path,
        required=True,
        help="Directory state DB path",
    )
    rollback_parser.add_argument(
        "--library-root",
        type=Path,
        required=True,
        dest="library_root",
        help="Library root directory (required for path validation)",
    )
    rollback_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )

    # Unjail command
    unjail_parser = subparsers.add_parser(
        "unjail",
        help="Reset a jailed directory to NEW state",
    )
    unjail_parser.add_argument(
        "dir_id",
        help="Directory identifier to unjail",
    )
    unjail_parser.add_argument(
        "--state-db",
        type=Path,
        required=True,
        help="Directory state DB path",
    )
    unjail_parser.add_argument(
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
                return run_resolve(
                    args,
                    store=store,
                    auto_probable=getattr(args, "auto_probable", False),
                    auto_probable_min_gap=getattr(args, "auto_probable_min_gap", 0.15),
                )
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

            # Construct a real provider client for identify
            cache_db = getattr(args, 'cache_db', None)
            provider_client = None
            fingerprint_reader = None
            app = None
            if cache_db:
                from .app import ResonanceApp
                app = ResonanceApp.from_env(
                    library_root=Path(args.directory).resolve(),
                    cache_path=cache_db,
                )
                provider_client = app.provider_client
                fingerprint_reader = app.fingerprint_reader

            if provider_client is None:
                # Try constructing from env without cache
                import os
                acoustid_key = os.getenv("ACOUSTID_API_KEY")
                discogs_token = os.getenv("DISCOGS_TOKEN")
                if not acoustid_key and not discogs_token:
                    print(
                        "Error: No provider credentials configured. "
                        "Set ACOUSTID_API_KEY or DISCOGS_TOKEN environment variables, "
                        "or provide --cache-db with cached provider data.",
                        file=sys.stderr,
                    )
                    return 2

            try:
                return run_identify(
                    args,
                    provider_client=provider_client,
                    fingerprint_reader=fingerprint_reader,
                )
            finally:
                if app is not None:
                    app.close()
        elif args.command == "plan":
            if not args.state_db:
                raise ValueError("state_db is required")
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.plan import run_plan
            from .app import ResonanceApp

            store = DirectoryStateStore(args.state_db)
            try:
                provider_client = None
                cache_db = getattr(args, "cache_db", None)
                library_root = getattr(args, "library_root", None)
                app = None
                if cache_db and library_root:
                    app = ResonanceApp.from_env(
                        library_root=Path(library_root).resolve(),
                        cache_path=cache_db,
                    )
                    provider_client = app.provider_client
                try:
                    return run_plan(args, store=store, provider_client=provider_client)
                finally:
                    if app is not None:
                        app.close()
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
        elif args.command == "decide":
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.decide import run_decide

            store = DirectoryStateStore(args.state_db)
            try:
                provider_client = None
                app = None
                cache_db = getattr(args, "cache_db", None)
                if cache_db:
                    from .app import ResonanceApp
                    offline = getattr(args, "offline", False)
                    app = ResonanceApp.from_env(
                        library_root=Path(args.library_root).resolve(),
                        cache_path=cache_db,
                        offline=offline,
                    )
                    provider_client = app.provider_client
                try:
                    return run_decide(args, store=store, provider_client=provider_client)
                finally:
                    if app is not None:
                        app.close()
            finally:
                store.close()
        elif args.command == "audit":
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.audit import run_audit

            store = DirectoryStateStore(args.state_db)
            try:
                result = run_audit(store=store, dir_id=args.dir_id)
                json_output = getattr(args, "json", False)
                if json_output:
                    import json
                    print(json.dumps(result, default=str))
                else:
                    for key, value in result.items():
                        print(f"{key}: {value}")
                return 0
            finally:
                store.close()
        elif args.command == "doctor":
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.doctor import run_doctor

            store = DirectoryStateStore(args.state_db)
            try:
                result = run_doctor(store=store, config_path=args.config)
                json_output = getattr(args, "json", False)
                if json_output:
                    import json
                    print(json.dumps(result, default=str))
                else:
                    issues = result.get("issues", [])
                    if not issues:
                        print("doctor: no issues found")
                    else:
                        for issue in issues:
                            print(f"doctor: {issue}")
                return 0
            finally:
                store.close()
        elif args.command == "rollback":
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.rollback import run_rollback

            if not args.report.exists():
                print(f"Error: Report file not found: {args.report}", file=sys.stderr)
                return 1

            import json
            with open(args.report, 'r') as f:
                report_data = json.load(f)

            # Convert report_data to a simple namespace for rollback
            from types import SimpleNamespace
            file_ops = [SimpleNamespace(**op) for op in report_data.get("file_ops", [])]
            tag_ops = [SimpleNamespace(**op) for op in report_data.get("tag_ops", [])]
            report = SimpleNamespace(
                file_ops=file_ops,
                tag_ops=tag_ops,
                errors=report_data.get("errors", []),
            )

            result = run_rollback(
                report=report,
                source_dir=Path("."),  # Will be derived from report
                destination_dir=Path("."),
                allowed_roots=(Path(args.library_root).resolve(),),
            )
            json_output = getattr(args, "json", False)
            if json_output:
                print(json.dumps(result, default=str))
            else:
                print(f"rollback: restored={result.get('restored', False)}")
            return 0
        elif args.command == "unjail":
            from .infrastructure.directory_store import DirectoryStateStore
            from .commands.unjail import run_unjail

            store = DirectoryStateStore(args.state_db)
            try:
                run_unjail(store=store, dir_id=args.dir_id)
                print(f"unjail: reset {args.dir_id} to NEW")
                return 0
            finally:
                store.close()
        else:
            parser.print_help()
            return 1
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
