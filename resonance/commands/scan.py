"""Scan command - discover directories and populate state DB."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import json
from typing import Iterable

from resonance.commands.output import emit_output
from resonance.errors import IOFailure, ValidationError, exit_code_for_exception
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.infrastructure.scanner import LibraryScanner


def _read_duration_seconds(path: Path) -> int | None:
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    duration = data.get("duration_seconds")
    return duration if isinstance(duration, int) else None


def _duration_total(files: Iterable[Path]) -> int:
    total = 0
    for path in files:
        duration = _read_duration_seconds(path)
        if isinstance(duration, int):
            total += duration
    return total


def _error_payload(library_root: Path, exc: BaseException) -> dict:
    return {
        "library_root": str(library_root),
        "status": "ERROR",
        "error_type": exc.__class__.__name__,
        "error_message": str(exc),
        "scanned": 0,
        "new": 0,
        "already_tracked": 0,
        "skipped": 0,
        "errors": 1,
    }


def run_scan(
    args: Namespace,
    *,
    store: DirectoryStateStore | None = None,
    scanner: LibraryScanner | None = None,
    output_sink=print,
) -> int:
    """Scan a library root and populate the state DB."""
    if store is None:
        raise ValidationError("store is required; construct it in the CLI composition root")
    library_root = Path(args.library_root).resolve()
    json_output = getattr(args, "json", False)
    if not library_root.exists():
        exc = IOFailure(f"Library root does not exist: {library_root}")
        emit_output(
            command="scan",
            payload=_error_payload(library_root, exc),
            json_output=json_output,
            output_sink=output_sink,
            human_lines=(f"scan: error={exc}",),
        )
        return exit_code_for_exception(exc)

    scanner = scanner or LibraryScanner([library_root])
    items: list[dict] = []
    scanned = 0
    new = 0
    already_tracked = 0
    skipped = 0
    errors = 0

    for batch in scanner.iter_directories():
        scanned += 1
        existing = store.get(batch.dir_id)
        signature_version = 1
        if (
            existing
            and existing.signature_hash == batch.signature_hash
            and existing.signature_version == signature_version
        ):
            already_tracked += 1
        else:
            new += 1

        record = store.get_or_create(
            batch.dir_id,
            batch.directory,
            batch.signature_hash,
            signature_version=signature_version,
        )
        items.append(
            {
                "dir_id": record.dir_id,
                "directory": str(record.last_seen_path),
                "signature_hash": record.signature_hash,
                "signature_version": record.signature_version,
                "track_count": len(batch.files),
                "total_duration_seconds": _duration_total(batch.files),
                "state": record.state.value,
            }
        )

    payload = {
        "library_root": str(library_root),
        "status": "OK",
        "scanned": scanned,
        "new": new,
        "already_tracked": already_tracked,
        "skipped": skipped,
        "errors": errors,
        "items": items,
    }
    emit_output(
        command="scan",
        payload=payload,
        json_output=json_output,
        output_sink=output_sink,
        human_lines=(
            f"scan: library_root={library_root}",
            f"scan: scanned={scanned} new={new} already_tracked={already_tracked} "
            f"skipped={skipped}",
        ),
    )
    return 0
