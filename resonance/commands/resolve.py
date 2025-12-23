"""Resolve command - resolve scanned directories using provider metadata."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from resonance.commands.output import emit_output
from resonance.core.identifier import extract_evidence
from resonance.core.resolver import ResolveOutcome, resolve_directory
from resonance.core.state import DirectoryState
from resonance.errors import IOFailure, ValidationError, exit_code_for_exception
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.infrastructure.scanner import LibraryScanner


def _error_payload(library_root: Path, exc: BaseException) -> dict:
    """Build error payload for resolve command."""
    return {
        "library_root": str(library_root),
        "status": "ERROR",
        "error_type": exc.__class__.__name__,
        "error_message": str(exc),
        "processed": 0,
        "resolved_auto": 0,
        "queued_prompt": 0,
        "skipped": 0,
        "errors": 1,
    }


def _resolve_item(outcome: ResolveOutcome, directory: Path) -> dict:
    """Build JSON item for a resolved directory."""
    item = {
        "dir_id": outcome.dir_id,
        "directory": str(directory),
        "state": outcome.state.value,
    }

    # Add resolution details if available
    if outcome.pinned_provider:
        item["provider"] = outcome.pinned_provider
    if outcome.pinned_release_id:
        item["release_id"] = outcome.pinned_release_id
    if outcome.pinned_confidence is not None:
        item["confidence"] = round(outcome.pinned_confidence, 2)  # type: ignore
    if outcome.scoring_version:
        item["scoring_version"] = outcome.scoring_version
    if outcome.reasons:
        item["reasons"] = list(outcome.reasons)  # type: ignore

    return item


def run_resolve(
    args: Namespace,
    *,
    store: DirectoryStateStore | None = None,
    provider_client=None,
    output_sink=print,
) -> int:
    """Resolve scanned directories using provider metadata."""
    if store is None:
        raise ValidationError("store is required; construct it in the CLI composition root")

    library_root = Path(args.library_root).resolve()
    json_output = getattr(args, "json", False)

    if not library_root.exists():
        exc = IOFailure(f"Library root does not exist: {library_root}")
        emit_output(
            command="resolve",
            payload=_error_payload(library_root, exc),
            json_output=json_output,
            output_sink=output_sink,
            human_lines=(f"resolve: error={exc}",),
        )
        return exit_code_for_exception(exc)

    # TODO: Get or create provider client from cache_db if provided
    # For now, provider_client should be passed in or will be None

    # Get directories that need resolution
    to_process = store.list_by_state(DirectoryState.NEW)

    items: list[dict] = []
    processed = 0
    resolved_auto = 0
    queued_prompt = 0
    skipped = 0
    errors = 0

    for record in to_process:
        processed += 1

        try:
            # Get audio files from directory
            audio_files = sorted(
                path
                for path in record.last_seen_path.iterdir()
                if path.is_file() and path.suffix.lower() in LibraryScanner.DEFAULT_EXTENSIONS
            )

            # Build evidence for identification
            evidence = extract_evidence(audio_files)

            # Resolve directory
            outcome = resolve_directory(
                dir_id=record.dir_id,
                path=record.last_seen_path,
                signature_hash=record.signature_hash,
                evidence=evidence,
                store=store,
                provider_client=provider_client,
            )

            # Count by outcome
            if outcome.state == DirectoryState.RESOLVED_AUTO:
                resolved_auto += 1
            elif outcome.state == DirectoryState.QUEUED_PROMPT:
                queued_prompt += 1
            elif outcome.state in (DirectoryState.RESOLVED_USER, DirectoryState.APPLIED):
                skipped += 1

            # Build item for JSON output
            items.append(_resolve_item(outcome, record.last_seen_path))

        except Exception as exc:
            errors += 1
            items.append({
                "dir_id": record.dir_id,
                "directory": str(record.last_seen_path),
                "state": "FAILED",
                "error": str(exc),
            })

    # Build and emit output
    payload = {
        "library_root": str(library_root),
        "status": "ERROR" if errors > 0 else "OK",
        "processed": processed,
        "resolved_auto": resolved_auto,
        "queued_prompt": queued_prompt,
        "skipped": skipped,
        "errors": errors,
        "items": items,
    }

    emit_output(
        command="resolve",
        payload=payload,
        json_output=json_output,
        output_sink=output_sink,
        human_lines=(
            f"resolve: library_root={library_root}",
            f"resolve: processed={processed} resolved_auto={resolved_auto} "
            f"queued_prompt={queued_prompt} skipped={skipped}",
        ),
    )

    return 0
