"""Deterministic ordering helpers for tests."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Any


def sorted_paths(paths: Iterable[Path]) -> list[Path]:
    """Return paths sorted by a stable, deterministic key."""
    return sorted(paths, key=lambda path: path.as_posix())


def stable_tiebreak(primary: Any, *parts: Any) -> tuple[Any, ...]:
    """Create a stable sort key with deterministic tiebreakers."""
    normalized: list[Any] = [primary]
    for part in parts:
        if isinstance(part, Path):
            normalized.append(part.as_posix())
        else:
            normalized.append(part if part is not None else "")
    return tuple(normalized)
