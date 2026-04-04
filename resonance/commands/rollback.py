"""Rollback command - revert applied file operations."""

from __future__ import annotations

import shutil
from pathlib import Path

from resonance.core.validation import SafePath


def run_rollback(
    *,
    report,
    source_dir: Path,
    destination_dir: Path,
    allowed_roots: tuple[Path, ...],
    tag_writer=None,
) -> dict[str, object]:
    """Rollback file moves using an ApplyReport.

    All paths from the report are validated against allowed_roots before
    any filesystem operations are performed.
    """
    if not allowed_roots:
        raise ValueError("allowed_roots is required for rollback")

    restored = False
    dest_to_source = {Path(op.destination_path): Path(op.source_path) for op in report.file_ops}

    # Validate all paths before performing any moves
    for op in report.file_ops:
        src = Path(op.source_path)
        dest = Path(op.destination_path)
        SafePath(src, allowed_roots)
        SafePath(dest, allowed_roots)

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
                SafePath(target, allowed_roots)
                if not target.exists() and target in dest_to_source:
                    target = dest_to_source[target]
                if target.exists():
                    tag_writer.write_tags_exact(target, dict(op.before_tags))
    return {
        "restored": restored,
        "errors": tuple(report.errors),
    }
