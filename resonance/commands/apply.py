"""Apply command - execute a stored plan."""

from __future__ import annotations

import os
from argparse import Namespace
from pathlib import Path

from resonance.core.applier import apply_plan
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.services.tag_writer import get_tag_writer
from resonance.settings import load_settings, resolve_tag_writer_backend


def run_apply(
    args: Namespace,
    *,
    apply_fn=apply_plan,
    config_loader=load_settings,
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
    if apply_fn is None:
        print("apply command not yet implemented")
        return 1
    if not args.plan:
        print("apply requires --plan")
        return 2
    if not args.state_db:
        print("apply requires --state-db")
        return 2
    print(f"Using tag writer backend: {backend}")
    apply_fn(tag_writer=writer, backend=backend)
    if apply_fn is not apply_plan:
        return 0
    store = DirectoryStateStore(Path(args.state_db))
    try:
        plan = None  # TODO: load plan artifact
        tag_patch = None  # TODO: load tag patch artifact
        if plan is None:
            print("apply plan loading not yet implemented")
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
    return 0
