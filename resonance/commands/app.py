"""Unified interactive app entrypoint."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Callable

from resonance.api.context import InvocationContext, InvocationMode
from resonance.api.service import ResonanceService
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


def run_app(
    args: Namespace,
    *,
    service: ResonanceService,
    input_provider: Callable[[str], str] = input,
    output_sink: Callable[[str], None] = print,
) -> int:
    """Run the singular interactive entrypoint for all major features."""
    context = InvocationContext(
        mode=InvocationMode.INTERACTIVE,
        json_output=getattr(args, "json", False),
    )

    output_sink("Resonance App")
    output_sink(f"library_root={Path(args.library_root).resolve()}")
    output_sink(f"state_db={Path(args.state_db).resolve()}")
    if getattr(args, "cache_db", None):
        output_sink(f"cache_db={Path(args.cache_db).resolve()}")

    while True:
        _show_status(args.state_db, output_sink)
        output_sink("Choose action:")
        output_sink("  1) decide")
        output_sink("  2) scan")
        output_sink("  3) resolve")
        output_sink("  4) prompt")
        output_sink("  5) plan")
        output_sink("  6) apply")
        output_sink("  7) audit")
        output_sink("  8) doctor")
        output_sink("  9) rollback")
        output_sink("  10) unjail")
        output_sink("  11) review summary")
        output_sink("  q) quit")

        choice = input_provider("app> ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            output_sink("bye")
            return 0

        if choice == "1":
            ns = Namespace(
                command="decide",
                library_root=args.library_root,
                state_db=args.state_db,
                cache_db=getattr(args, "cache_db", None),
                offline=getattr(args, "offline", False),
                decisions_file=None,
                json=getattr(args, "json", False),
                auto_probable=getattr(args, "auto_probable", False),
                auto_probable_min_gap=getattr(args, "auto_probable_min_gap", 0.15),
                plan_dir=getattr(args, "plan_dir", None),
                headless=False,
                fail_on_prompt=False,
                mode="interactive",
            )
            _run_action(service, ns, context, input_provider, output_sink)
            continue

        if choice == "2":
            ns = Namespace(
                command="scan",
                library_root=args.library_root,
                state_db=args.state_db,
                json=getattr(args, "json", False),
                mode="interactive",
            )
            _run_action(service, ns, context, input_provider, output_sink)
            continue

        if choice == "3":
            ns = Namespace(
                command="resolve",
                library_root=args.library_root,
                state_db=args.state_db,
                cache_db=getattr(args, "cache_db", None),
                offline=getattr(args, "offline", False),
                json=getattr(args, "json", False),
                auto_probable=getattr(args, "auto_probable", False),
                auto_probable_min_gap=getattr(args, "auto_probable_min_gap", 0.15),
                mode="interactive",
            )
            _run_action(service, ns, context, input_provider, output_sink)
            continue

        if choice == "4":
            ns = Namespace(
                command="prompt",
                state_db=args.state_db,
                cache_db=getattr(args, "cache_db", None),
                decisions_file=None,
                record_replay=None,
                replay_file=None,
                json=getattr(args, "json", False),
                mode="interactive",
            )
            _run_action(service, ns, context, input_provider, output_sink)
            continue

        if choice == "5":
            dir_id = input_provider("dir_id: ").strip()
            if not dir_id:
                output_sink("plan: dir_id is required")
                continue
            ns = Namespace(
                command="plan",
                dir_id=dir_id,
                state_db=args.state_db,
                cache_db=getattr(args, "cache_db", None),
                library_root=args.library_root,
                plan_dir=getattr(args, "plan_dir", None),
                json=getattr(args, "json", False),
                mode="interactive",
            )
            _run_action(service, ns, context, input_provider, output_sink)
            continue

        if choice == "6":
            plan_path = input_provider("plan path: ").strip()
            if not plan_path:
                output_sink("apply: plan path is required")
                continue
            ns = Namespace(
                command="apply",
                plan=Path(plan_path),
                state_db=args.state_db,
                config=getattr(args, "config", Path.home() / ".config" / "resonance" / "settings.json"),
                tag_writer_backend=getattr(args, "tag_writer_backend", None),
                json=getattr(args, "json", False),
                tag_patch=None,
                no_dry_run=False,
                library_root=args.library_root,
                mode="interactive",
            )
            if not _confirm(input_provider, "Apply plan in dry-run mode? [y/N]: "):
                output_sink("apply: cancelled")
                continue
            _run_action(service, ns, context, input_provider, output_sink)
            continue

        if choice == "7":
            dir_id = input_provider("dir_id: ").strip()
            if not dir_id:
                output_sink("audit: dir_id is required")
                continue
            ns = Namespace(
                command="audit",
                dir_id=dir_id,
                state_db=args.state_db,
                json=getattr(args, "json", False),
                mode="interactive",
            )
            _run_action(service, ns, context, input_provider, output_sink)
            continue

        if choice == "8":
            ns = Namespace(
                command="doctor",
                state_db=args.state_db,
                config=getattr(args, "config", Path.home() / ".config" / "resonance" / "settings.json"),
                json=getattr(args, "json", False),
                mode="interactive",
            )
            _run_action(service, ns, context, input_provider, output_sink)
            continue

        if choice == "9":
            report_path = input_provider("report path: ").strip()
            if not report_path:
                output_sink("rollback: report path is required")
                continue
            ns = Namespace(
                command="rollback",
                report=Path(report_path),
                state_db=args.state_db,
                library_root=args.library_root,
                json=getattr(args, "json", False),
                mode="interactive",
            )
            if not _confirm(input_provider, "Rollback operations from report? [y/N]: "):
                output_sink("rollback: cancelled")
                continue
            _run_action(service, ns, context, input_provider, output_sink)
            continue

        if choice == "10":
            dir_id = input_provider("dir_id: ").strip()
            if not dir_id:
                output_sink("unjail: dir_id is required")
                continue
            ns = Namespace(
                command="unjail",
                dir_id=dir_id,
                state_db=args.state_db,
                json=getattr(args, "json", False),
                mode="interactive",
            )
            _run_action(service, ns, context, input_provider, output_sink)
            continue

        if choice == "11":
            _show_review_summary(args.state_db, output_sink)
            continue

        output_sink("Unknown action")


def _run_action(
    service: ResonanceService,
    ns: Namespace,
    context: InvocationContext,
    input_provider: Callable[[str], str],
    output_sink: Callable[[str], None],
) -> None:
    """Run one action and keep app shell alive on failure."""
    try:
        code = service.execute_namespace(
            ns,
            context=context,
            input_provider=input_provider,
            output_sink=output_sink,
        )
        if code != 0:
            output_sink(f"{ns.command}: exited with code {code}")
    except Exception as exc:
        output_sink(f"{ns.command}: failed: {exc}")


def _confirm(input_provider: Callable[[str], str], prompt: str) -> bool:
    """Simple y/N confirmation for risky actions."""
    return input_provider(prompt).strip().lower() in {"y", "yes"}


def _show_status(state_db: Path, output_sink: Callable[[str], None]) -> None:
    """Show workload summary in app shell."""
    store = DirectoryStateStore(state_db)
    try:
        counts = {
            "new": len(store.list_by_state(DirectoryState.NEW)),
            "queued_prompt": len(store.list_by_state(DirectoryState.QUEUED_PROMPT)),
            "resolved_auto": len(store.list_by_state(DirectoryState.RESOLVED_AUTO)),
            "resolved_user": len(store.list_by_state(DirectoryState.RESOLVED_USER)),
            "planned": len(store.list_by_state(DirectoryState.PLANNED)),
            "applied": len(store.list_by_state(DirectoryState.APPLIED)),
            "jailed": len(store.list_by_state(DirectoryState.JAILED)),
        }
    finally:
        store.close()

    output_sink(
        "status: "
        + ", ".join(f"{key}={value}" for key, value in counts.items())
    )


def _show_review_summary(state_db: Path, output_sink: Callable[[str], None]) -> None:
    """Show a concise review-oriented summary for quick triage."""
    store = DirectoryStateStore(state_db)
    try:
        queued = store.list_by_state(DirectoryState.QUEUED_PROMPT)
        jailed = store.list_by_state(DirectoryState.JAILED)
        planned = store.list_by_state(DirectoryState.PLANNED)
        output_sink("review: queued_prompt directories")
        if not queued:
            output_sink("  none")
        else:
            for record in queued[:10]:
                output_sink(f"  - {record.dir_id} :: {record.last_seen_path}")
            if len(queued) > 10:
                output_sink(f"  ... and {len(queued) - 10} more")

        output_sink(f"review: jailed={len(jailed)} planned={len(planned)}")
    finally:
        store.close()
