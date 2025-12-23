"""Rollback command - revert applied file operations."""

from __future__ import annotations

import shutil
from pathlib import Path


def run_rollback(
    *, report, source_dir: Path, destination_dir: Path, tag_writer=None
) -> dict[str, object]:
    """Rollback file moves using an ApplyReport."""
    restored = False
    dest_to_source = {Path(op.destination_path): Path(op.source_path) for op in report.file_ops}
    for op in report.file_ops:
        src = Path(op.source_path)
        dest = Path(op.destination_path)
        if dest.exists():
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(src))
            restored = True
    if tag_writer is not None:
        for op in report.tag_ops:
            if op.before_tags:
                target = Path(op.file_path)
                if not target.exists() and target in dest_to_source:
                    target = dest_to_source[target]
                if target.exists():
                    tag_writer.write_tags_exact(target, dict(op.before_tags))
    return {
        "restored": restored,
        "errors": tuple(report.errors),
    }
