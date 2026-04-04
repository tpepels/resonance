"""Deterministic CLI output helpers."""

from __future__ import annotations

import json
from typing import Iterable

SCHEMA_VERSION = "v1"


def build_envelope(*, command: str, payload: dict) -> dict:
    """Build a stable JSON envelope used by all command outputs."""
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "data": payload,
    }


def validate_envelope_shape(envelope: dict) -> None:
    """Validate minimal schema shape for regression tests and guards."""
    required_keys = {"schema_version", "command", "data"}
    missing = required_keys.difference(envelope.keys())
    if missing:
        raise ValueError(f"Envelope missing keys: {sorted(missing)}")
    if envelope.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Envelope schema_version must be {SCHEMA_VERSION}")
    if not isinstance(envelope.get("command"), str):
        raise ValueError("Envelope command must be a string")
    if not isinstance(envelope.get("data"), dict):
        raise ValueError("Envelope data must be an object")


def emit_output(
    *,
    command: str,
    payload: dict,
    json_output: bool,
    output_sink=print,
    human_lines: Iterable[str] = (),
) -> None:
    """Emit deterministic CLI output."""
    if json_output:
        envelope = build_envelope(command=command, payload=payload)
        output_sink(
            json.dumps(
                envelope,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
        )
        return
    for line in human_lines:
        output_sink(line)


def build_error_payload(*, library_root: str, exc: BaseException, counters: dict[str, int]) -> dict:
    """Build a standard command error payload with command-specific counters."""
    payload: dict[str, object] = {
        "library_root": library_root,
        "status": "ERROR",
        "error_type": exc.__class__.__name__,
        "error_message": str(exc),
    }
    payload.update(counters)
    return payload
