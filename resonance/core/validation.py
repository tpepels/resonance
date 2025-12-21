"""Input validation helpers for safety-critical identifiers."""

from __future__ import annotations

import re
from pathlib import Path


def _is_within(parent: Path, child: Path) -> bool:
    parent = parent.resolve()
    child = child.resolve()
    return parent == child or parent in child.parents

DIR_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
SIGNATURE_HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
RELEASE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._:-]{1,128}$")


def validate_dir_id(dir_id: str) -> None:
    if not DIR_ID_PATTERN.match(dir_id):
        raise ValueError(f"Invalid dir_id format: {dir_id}")


def validate_signature_hash(signature_hash: str) -> None:
    if not SIGNATURE_HASH_PATTERN.match(signature_hash):
        raise ValueError(f"Invalid signature_hash format: {signature_hash}")


def validate_release_id(release_id: str) -> None:
    if not RELEASE_ID_PATTERN.match(release_id):
        raise ValueError(f"Invalid release_id format: {release_id}")


class SafePath:
    """Validated, resolved path within allowed roots."""

    def __init__(self, path: Path, allowed_roots: tuple[Path, ...]) -> None:
        if ".." in path.parts:
            raise ValueError(f"Path traversal not allowed: {path}")
        resolved = path.resolve()
        if not any(_is_within(root, resolved) for root in allowed_roots):
            raise ValueError(f"Path outside allowed roots: {path}")
        self.path = resolved
