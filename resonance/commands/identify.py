"""Identify command - score releases for a directory."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from resonance.commands.output import emit_output
from resonance.core.identifier import (
    DirectoryEvidence,
    IdentificationResult,
    ProviderClient,
    extract_evidence,
    identify,
)
from resonance.infrastructure.scanner import LibraryScanner


def _format_candidates(result: IdentificationResult) -> list[dict]:
    return [
        {
            "provider": candidate.release.provider,
            "release_id": candidate.release.release_id,
            "title": candidate.release.title,
            "artist": candidate.release.artist,
            "total_score": candidate.total_score,
            "fingerprint_coverage": candidate.fingerprint_coverage,
            "track_count_match": candidate.track_count_match,
            "duration_fit": candidate.duration_fit,
        }
        for candidate in result.candidates
    ]


def _identify_payload(
    *,
    batch,
    result: IdentificationResult,
) -> dict:
    return {
        "directory": str(batch.directory),
        "dir_id": batch.dir_id,
        "signature_hash": batch.signature_hash,
        "tier": result.tier.value,
        "reasons": list(result.reasons),
        "scoring_version": result.scoring_version,
        "candidates": _format_candidates(result),
        "track_count": result.evidence.track_count,
        "total_duration_seconds": result.evidence.total_duration_seconds,
    }


def run_identify(
    args: Namespace,
    *,
    provider_client: ProviderClient | None = None,
    evidence_builder=None,
    output_sink=print,
) -> int:
    """Identify a directory and emit a deterministic result."""
    directory = Path(args.directory).resolve()
    scanner = LibraryScanner([directory])
    batch = scanner.collect_directory(directory)
    if not batch:
        emit_output(
            command="identify",
            payload={
                "directory": str(directory),
                "status": "NO_AUDIO",
            },
            json_output=getattr(args, "json", False),
            output_sink=output_sink,
            human_lines=(f"identify: no audio files in {directory}",),
        )
        return 1

    if provider_client is None:
        emit_output(
            command="identify",
            payload={
                "directory": str(directory),
                "status": "NO_PROVIDER",
                "provider_status": "NOT_CONFIGURED",
            },
            json_output=getattr(args, "json", False),
            output_sink=output_sink,
            human_lines=("identify: provider client not configured",),
        )
        return 2

    evidence_builder = evidence_builder or extract_evidence
    evidence: DirectoryEvidence = evidence_builder(batch.files)
    result = identify(evidence, provider_client)
    payload = _identify_payload(batch=batch, result=result)
    emit_output(
        command="identify",
        payload=payload,
        json_output=getattr(args, "json", False),
        output_sink=output_sink,
        human_lines=(
            f"identify: dir_id={payload['dir_id']} tier={payload['tier']}",
            f"identify: candidates={len(payload['candidates'])} "
            f"tracks={payload['track_count']}",
        ),
    )
    return 0
