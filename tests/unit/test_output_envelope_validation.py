"""Tests for command output envelope shape governance."""

from __future__ import annotations

import pytest

from resonance.commands.output import build_envelope, validate_envelope_shape


def test_build_envelope_has_required_shape() -> None:
    envelope = build_envelope(command="scan", payload={"status": "OK"})
    validate_envelope_shape(envelope)


def test_validate_envelope_shape_rejects_missing_keys() -> None:
    with pytest.raises(ValueError, match="missing keys"):
        validate_envelope_shape({"command": "scan"})


def test_validate_envelope_shape_rejects_bad_types() -> None:
    with pytest.raises(ValueError, match="data must be an object"):
        validate_envelope_shape({"schema_version": "v1", "command": "scan", "data": []})
