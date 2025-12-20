"""Rollback command - revert applied file operations."""

from __future__ import annotations

import shutil
from pathlib import Path


def run_rollback(*, report, source_dir: Path, destination_dir: Path) -> dict[str, object]:
    """Rollback file moves using an ApplyReport."""
    restored = False
    for op in report.file_ops:
        src = Path(op.source_path)
        dest = Path(op.destination_path)
        if dest.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(src))
            restored = True
    return {
        "restored": restored,
        "errors": tuple(report.errors),
    }
