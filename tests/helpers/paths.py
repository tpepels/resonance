"""Path helpers for deterministic, sanitized test fixtures."""

from __future__ import annotations

from pathlib import Path

from resonance.core.planner import sanitize_filename


def sanitized_dir(base: Path, name: str) -> Path:
    """Create a deterministic, sanitized directory under base."""
    path = base / sanitize_filename(name)
    path.mkdir(parents=True, exist_ok=True)
    return path
