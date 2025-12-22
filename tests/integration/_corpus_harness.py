"""Shared corpus test harness for snapshot-driven integration tests.

This module provides common snapshot mechanics for both golden and real-world
corpus testing. It enforces deterministic JSON serialization, regen gating,
and stable tag filtering.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

# NOTE: Keep tag filtering policy aligned with golden.
PROV_KEYS = (
    "resonance.prov.version",
    "resonance.prov.tool",
    "resonance.prov.tool_version",
    "resonance.prov.dir_id",
    "resonance.prov.pinned_provider",
    "resonance.prov.pinned_release_id",
    "resonance.prov.applied_at_utc",
)


def is_regen_enabled(env_var: str) -> bool:
    """Check if snapshot regeneration is enabled via environment variable."""
    return os.environ.get(env_var) == "1"


def snapshot_path(expected_root: Path, scenario: str, name: str) -> Path:
    """Compute path to snapshot artifact."""
    return expected_root / scenario / name


def assert_or_write_snapshot(
    *,
    path: Path,
    payload: Any,
    regen: bool,
    regen_env_var: str,
) -> None:
    """Write snapshot in regen mode; assert equality otherwise.

    Args:
        path: Snapshot file path
        payload: Data to snapshot (must be JSON-serializable)
        regen: Whether to regenerate snapshot
        regen_env_var: Name of env var that controls regen (for error message)

    Raises:
        FileNotFoundError: If snapshot missing and not in regen mode
        AssertionError: If payload does not match existing snapshot
    """
    if regen:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        return

    if not path.exists():
        raise FileNotFoundError(
            f"Missing snapshot: {path}. Set {regen_env_var}=1 to create."
        )

    expected = json.loads(path.read_text())
    assert payload == expected


def filter_relevant_tags(tags: dict[str, str]) -> dict[str, str]:
    """Extract provenance and core music tags for snapshot comparison.

    Args:
        tags: Full tag dictionary

    Returns:
        Filtered tag dict containing only stable, relevant keys
    """
    filtered: dict[str, str] = {k: tags[k] for k in PROV_KEYS if k in tags}
    for key in ("album", "albumartist", "title", "tracknumber"):
        if key in tags:
            filtered[key] = tags[key]
    return filtered


def assert_valid_plan_hash(tags: dict[str, str]) -> None:
    """Assert that plan_hash tag exists and is a valid SHA-256 hex digest.

    Args:
        tags: Tag dictionary to validate

    Raises:
        AssertionError: If plan_hash missing or malformed
    """
    plan_hash = tags.get("resonance.prov.plan_hash")
    assert plan_hash is not None
    assert re.fullmatch(r"[0-9a-f]{64}", plan_hash)
