"""Apply command - execute a stored plan."""

from __future__ import annotations

import os
from argparse import Namespace
from pathlib import Path

from resonance.commands.output import emit_output
from resonance.errors import ValidationError
from resonance.core.applier import ApplyReport, ApplyStatus, apply_plan
from resonance.core.artifacts import load_plan, load_tag_patch
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import get_tag_writer
from resonance.settings import load_settings, resolve_tag_writer_backend


def run_apply(
    args: Namespace,
    *,
    apply_fn=apply_plan,
    config_loader=load_settings,
    store: DirectoryStateStore | None = None,
    output_sink=print,
) -> int:
    """Resolve tag writer backend and dispatch apply."""
    config_path = Path(args.config).expanduser() if args.config else None
    settings = config_loader(config_path)
    backend = resolve_tag_writer_backend(
        cli_backend=args.tag_writer_backend,
        env_backend=os.getenv("RESONANCE_TAG_WRITER_BACKEND"),
        config_backend=settings.tag_writer_backend,
    )
    writer = get_tag_writer(backend)
    json_output = getattr(args, "json", False)
    if apply_fn is None:
        emit_output(
            command="apply",
            payload={"status": "NOT_IMPLEMENTED"},
            json_output=json_output,
            output_sink=output_sink,
            human_lines=("apply: not implemented",),
        )
        return 1
    if not args.plan:
        emit_output(
            command="apply",
            payload={"status": "MISSING_PLAN"},
            json_output=json_output,
            output_sink=output_sink,
            human_lines=("apply: missing --plan",),
        )
        raise ValidationError("apply requires --plan")
    if not args.state_db:
        emit_output(
            command="apply",
            payload={"status": "MISSING_STATE_DB"},
            json_output=json_output,
            output_sink=output_sink,
            human_lines=("apply: missing --state-db",),
        )
        raise ValidationError("apply requires --state-db")
    if not json_output:
        output_sink(f"Using tag writer backend: {backend}")
    if store is None:
        raise ValidationError("store is required; construct it in the CLI composition root")
    try:
        library_root = getattr(args, "library_root", None)
        if not library_root:
            emit_output(
                command="apply",
                payload={"status": "MISSING_LIBRARY_ROOT"},
                json_output=json_output,
                output_sink=output_sink,
                human_lines=("apply: --library-root is required",),
            )
            raise ValidationError("apply requires --library-root")
        allowed_roots: tuple[Path, ...] = (Path(library_root).resolve(),)
        try:
            plan = load_plan(Path(args.plan), allowed_roots=allowed_roots)
        except (OSError, ValueError) as exc:
            emit_output(
                command="apply",
                payload={"status": "PLAN_LOAD_ERROR", "error": str(exc)},
                json_output=json_output,
                output_sink=output_sink,
                human_lines=(f"apply: plan load error: {exc}",),
            )
            return 1
        tag_patch = None
        if getattr(args, "tag_patch", None):
            try:
                tag_patch = load_tag_patch(Path(args.tag_patch))
            except (OSError, ValueError) as exc:
                emit_output(
                    command="apply",
                    payload={"status": "TAG_PATCH_LOAD_ERROR", "error": str(exc)},
                    json_output=json_output,
                    output_sink=output_sink,
                    human_lines=(f"apply: tag patch load error: {exc}",),
                )
                return 1
        dry_run = not getattr(args, "no_dry_run", False)
        result = apply_fn(
            plan,
            tag_patch,
            store,
            allowed_roots=allowed_roots,
            dry_run=dry_run,
            tag_writer=writer,
        )
    finally:
        store.close()
    payload = {
        "status": result.status.value,
        "backend": backend,
        "dry_run": result.dry_run,
        "plan_version": result.plan_version,
        "errors": list(result.errors),
        "warnings": list(result.warnings),
    }
    emit_output(
        command="apply",
        payload=payload,
        json_output=json_output,
        output_sink=output_sink,
        human_lines=(f"apply: status={payload['status']} dry_run={payload['dry_run']}",),
    )
    return 0 if result.status in (ApplyStatus.APPLIED, ApplyStatus.NOOP_ALREADY_APPLIED) else 1
