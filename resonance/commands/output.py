"""Deterministic CLI output helpers."""

from __future__ import annotations

import json
from typing import Iterable

SCHEMA_VERSION = "v1"


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
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "command": command,
            "data": payload,
        }
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
