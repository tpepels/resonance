"""Snapshot helpers for deterministic Plan JSON assertions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def serialize_plan(plan: Mapping[str, Any]) -> str:
    """Serialize a plan with stable formatting."""
    return json.dumps(plan, sort_keys=True, indent=2) + "\n"


def assert_plan_snapshot(
    plan: Mapping[str, Any],
    snapshot_path: Path,
    *,
    update: bool = False,
) -> None:
    """Assert that a plan matches the snapshot on disk."""
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = serialize_plan(plan)

    if update or not snapshot_path.exists():
        snapshot_path.write_text(rendered)
        return

    expected = snapshot_path.read_text()
    assert rendered == expected
