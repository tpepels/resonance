"""Plan command - create deterministic plan artifact."""

from __future__ import annotations

from argparse import Namespace
import hashlib
from pathlib import Path

from resonance.commands.output import emit_output
from resonance.errors import ValidationError
from resonance.core.identifier import ProviderClient, ProviderRelease
from resonance.core.artifacts import serialize_plan
from resonance.core.planner import plan_directory
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


def _plan_payload(plan) -> dict:
    return {
        "dir_id": plan.dir_id,
        "signature_hash": plan.signature_hash,
        "plan_version": plan.plan_version,
        "destination_path": str(plan.destination_path),
        "operations_count": len(plan.operations),
        "conflict_policy": plan.conflict_policy,
        "non_audio_policy": plan.non_audio_policy,
    }


def run_plan(
    args: Namespace,
    *,
    store: DirectoryStateStore | None = None,
    pinned_release: ProviderRelease | None = None,
    provider_client: ProviderClient | None = None,
    canonicalize_display=None,
    output_sink=print,
    output_dir: Path | None = None,
) -> int:
    """Generate a plan for a resolved directory.

    If output_dir is provided, the plan artifact JSON is written to
    ``output_dir/<dir_id>.plan.json``.
    """
    if store is None:
        raise ValidationError("store is required; construct it in the CLI composition root")

    try:
        record = store.get(args.dir_id)
        if not record:
            raise ValidationError(f"Directory {args.dir_id} not found in store")
        if pinned_release is None:
            if not record.pinned_provider or not record.pinned_release_id:
                raise ValidationError(
                    "directory is not pinned; resolve/prompt must run before plan"
                )
            if provider_client is None:
                raise ValidationError(
                    "provider_client is required when pinned_release is not injected"
                )
            pinned_release = provider_client.release_by_id(
                record.pinned_provider,
                record.pinned_release_id,
            )
            if pinned_release is None:
                raise ValidationError(
                    "failed to load pinned release from provider; check provider credentials/cache"
                )
        plan = plan_directory(
            record=record,
            pinned_release=pinned_release,
            canonicalize_display=canonicalize_display,
        )
        plan_hash = hashlib.sha256(serialize_plan(plan).encode("utf-8")).hexdigest()
        store.record_plan_summary(plan.dir_id, plan_hash, plan.plan_version)
        store.set_state(
            plan.dir_id,
            DirectoryState.PLANNED,
            pinned_provider=record.pinned_provider,
            pinned_release_id=record.pinned_release_id,
        )
        # Write plan artifact to disk when output_dir is provided
        plan_path = None
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            plan_path = output_dir / f"{plan.dir_id}.plan.json"
            plan_path.write_text(serialize_plan(plan), encoding="utf-8")
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"plan generation failed: {exc}") from exc

    payload = _plan_payload(plan)
    if plan_path is not None:
        payload["plan_path"] = str(plan_path)
    emit_output(
        command="plan",
        payload=payload,
        json_output=getattr(args, "json", False),
        output_sink=output_sink,
        human_lines=(
            f"plan: dir_id={payload['dir_id']} ops={payload['operations_count']}",
            f"plan: destination={payload['destination_path']}",
        ),
    )
    return 0
