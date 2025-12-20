"""Apply command - execute a stored plan."""

from __future__ import annotations

import os
from argparse import Namespace
from pathlib import Path

from resonance.commands.output import emit_output
from resonance.core.applier import ApplyReport, ApplyStatus, apply_plan
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import get_tag_writer
from resonance.settings import load_settings, resolve_tag_writer_backend


def run_apply(
    args: Namespace,
    *,
    apply_fn=apply_plan,
    config_loader=load_settings,
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
        return 2
    if not args.state_db:
        emit_output(
            command="apply",
            payload={"status": "MISSING_STATE_DB"},
            json_output=json_output,
            output_sink=output_sink,
            human_lines=("apply: missing --state-db",),
        )
        return 2
    if not json_output:
        output_sink(f"Using tag writer backend: {backend}")
    result = apply_fn(tag_writer=writer, backend=backend)
    if apply_fn is not apply_plan:
        payload = {
            "status": "OK",
            "backend": backend,
        }
        if isinstance(result, ApplyReport):
            payload.update(
                {
                    "status": result.status.value,
                    "plan_version": result.plan_version,
                    "tagpatch_version": result.tagpatch_version,
                    "errors": list(result.errors),
                }
            )
        emit_output(
            command="apply",
            payload=payload,
            json_output=json_output,
            output_sink=output_sink,
            human_lines=(f"apply: status={payload['status']}",),
        )
        return 0
    store = DirectoryStateStore(Path(args.state_db))
    try:
        plan = None  # TODO: load plan artifact
        tag_patch = None  # TODO: load tag patch artifact
        if plan is None:
            emit_output(
                command="apply",
                payload={"status": "PLAN_LOAD_NOT_IMPLEMENTED"},
                json_output=json_output,
                output_sink=output_sink,
                human_lines=("apply: plan loading not implemented",),
            )
            return 1
        apply_fn(
            plan,
            tag_patch,
            store,
            allowed_roots=(),
            dry_run=True,
            tag_writer=writer,
        )
    finally:
        store.close()
    emit_output(
        command="apply",
        payload={"status": ApplyStatus.APPLIED.value, "backend": backend},
        json_output=json_output,
        output_sink=output_sink,
        human_lines=("apply: status=APPLIED",),
    )
    return 0
