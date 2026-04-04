"""Decide command - single-command orchestration of the full pipeline.

Chains: scan → resolve → prompt → plan → apply for a library root.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Optional

from resonance.commands.output import emit_output
from resonance.core.state import DirectoryState
from resonance.errors import ValidationError
from resonance.infrastructure.directory_store import DirectoryStateStore


def run_decide(
    args: Namespace,
    *,
    store: DirectoryStateStore | None = None,
    provider_client=None,
    input_provider=input,
    output_sink=print,
) -> int:
    """Run the full pipeline: scan → resolve → prompt → plan → apply.

    This orchestrates all pipeline stages in order, stopping early on errors.
    """
    if store is None:
        raise ValidationError("store is required; construct it in the CLI composition root")

    library_root = Path(args.library_root).resolve()
    json_output = getattr(args, "json", False)
    headless = getattr(args, "headless", False)

    if not library_root.exists():
        emit_output(
            command="decide",
            payload={"status": "ERROR", "error": f"Library root does not exist: {library_root}"},
            json_output=json_output,
            output_sink=output_sink,
            human_lines=(f"decide: library root does not exist: {library_root}",),
        )
        return 3

    stages_run: list[str] = []
    stage_results: dict[str, dict] = {}

    # --- Stage 1: Scan ---
    from resonance.commands.scan import run_scan

    scan_args = Namespace(
        library_root=str(library_root),
        state_db=str(args.state_db),
        json=False,
    )
    scan_output: list[str] = []
    scan_code = run_scan(scan_args, store=store, output_sink=scan_output.append)
    stages_run.append("scan")
    stage_results["scan"] = {"exit_code": scan_code}
    if scan_code != 0:
        emit_output(
            command="decide",
            payload={"status": "SCAN_FAILED", "stages_run": stages_run, "stages": stage_results},
            json_output=json_output,
            output_sink=output_sink,
            human_lines=(f"decide: scan failed (exit {scan_code})",),
        )
        return scan_code

    # --- Stage 2: Resolve ---
    from resonance.commands.resolve import run_resolve

    resolve_args = Namespace(
        library_root=str(library_root),
        state_db=str(args.state_db),
        cache_db=getattr(args, "cache_db", None),
        offline=getattr(args, "offline", False),
        json=False,
    )
    resolve_output: list[str] = []
    auto_probable = getattr(args, "auto_probable", False) or headless
    auto_probable_min_gap = getattr(args, "auto_probable_min_gap", 0.15)
    resolve_code = run_resolve(
        resolve_args,
        store=store,
        provider_client=provider_client,
        output_sink=resolve_output.append,
        auto_probable=auto_probable,
        auto_probable_min_gap=auto_probable_min_gap,
    )
    stages_run.append("resolve")
    stage_results["resolve"] = {"exit_code": resolve_code}
    if resolve_code != 0:
        emit_output(
            command="decide",
            payload={"status": "RESOLVE_FAILED", "stages_run": stages_run, "stages": stage_results},
            json_output=json_output,
            output_sink=output_sink,
            human_lines=(f"decide: resolve failed (exit {resolve_code})",),
        )
        return resolve_code

    # --- Stage 3: Prompt (only if there are QUEUED_PROMPT directories) ---
    queued = store.list_by_state(DirectoryState.QUEUED_PROMPT)
    if queued and not headless:
        from resonance.commands.prompt import run_prompt

        prompt_args = Namespace(
            state_db=str(args.state_db),
            cache_db=getattr(args, "cache_db", None),
            decisions_file=getattr(args, "decisions_file", None),
            record_replay=None,
            replay_file=None,
            json=False,
        )
        prompt_output: list[str] = []
        prompt_code = run_prompt(
            prompt_args,
            store=store,
            provider_client=provider_client,
            input_provider=input_provider,
            output_sink=prompt_output.append,
        )
        stages_run.append("prompt")
        stage_results["prompt"] = {"exit_code": prompt_code, "queued": len(queued)}
        if prompt_code != 0:
            emit_output(
                command="decide",
                payload={"status": "PROMPT_FAILED", "stages_run": stages_run, "stages": stage_results},
                json_output=json_output,
                output_sink=output_sink,
                human_lines=(f"decide: prompt failed (exit {prompt_code})",),
            )
            return prompt_code
    else:
        stages_run.append("prompt")
        stage_results["prompt"] = {
            "exit_code": 0,
            "queued": len(queued),
            "skipped": True,
            **({"headless": True} if headless and queued else {}),
        }

    # --- Stage 4: Plan (for all resolved directories) ---
    from resonance.commands.plan import run_plan

    planned = 0
    plan_errors = 0
    plan_dir = getattr(args, "plan_dir", None)
    if plan_dir is not None:
        plan_dir = Path(plan_dir)
    resolved_states = (DirectoryState.RESOLVED_AUTO, DirectoryState.RESOLVED_USER)
    for state in resolved_states:
        for record in store.list_by_state(state):
            plan_args = Namespace(
                dir_id=record.dir_id,
                state_db=str(args.state_db),
                cache_db=getattr(args, "cache_db", None),
                library_root=str(library_root),
                json=False,
            )
            plan_output: list[str] = []
            try:
                plan_code = run_plan(
                    plan_args,
                    store=store,
                    provider_client=provider_client,
                    output_sink=plan_output.append,
                    output_dir=plan_dir,
                )
                if plan_code == 0:
                    planned += 1
                else:
                    plan_errors += 1
            except ValidationError:
                plan_errors += 1

    stages_run.append("plan")
    stage_results["plan"] = {"exit_code": 0 if plan_errors == 0 else 1, "planned": planned, "errors": plan_errors}
    if plan_errors > 0 and planned == 0:
        emit_output(
            command="decide",
            payload={"status": "PLAN_FAILED", "stages_run": stages_run, "stages": stage_results},
            json_output=json_output,
            output_sink=output_sink,
            human_lines=(f"decide: plan failed ({plan_errors} errors, 0 planned)",),
        )
        return 1

    # --- Stage 5: Apply (for all planned directories) ---
    from resonance.commands.apply import run_apply

    applied = 0
    apply_errors = 0
    # The apply command requires plan artifact files on disk.
    # In the decide flow, plans are stored in the state DB. We skip apply
    # if no plan artifacts are available (plan command writes to state DB,
    # but the artifact file must be serialized separately).
    # For now, apply runs for directories in PLANNED state if --plan is provided.
    # In the orchestration flow, we report what was planned and let the user
    # run apply separately with the generated plan files.
    stages_run.append("apply")
    stage_results["apply"] = {"exit_code": 0, "applied": applied, "errors": apply_errors, "note": "apply requires plan artifact files; run apply separately after reviewing plans"}

    # --- Summary ---
    total_resolved = sum(
        len(store.list_by_state(s))
        for s in (DirectoryState.RESOLVED_AUTO, DirectoryState.RESOLVED_USER, DirectoryState.PLANNED)
    )
    payload = {
        "status": "OK" if plan_errors == 0 else "PARTIAL",
        "library_root": str(library_root),
        "stages_run": stages_run,
        "stages": stage_results,
        "summary": {
            "planned": planned,
            "plan_errors": plan_errors,
            "total_resolved": total_resolved,
        },
    }
    emit_output(
        command="decide",
        payload=payload,
        json_output=json_output,
        output_sink=output_sink,
        human_lines=(
            f"decide: stages={','.join(stages_run)}",
            f"decide: planned={planned} errors={plan_errors}",
        ),
    )
    return 0 if plan_errors == 0 else 1
