"""Integration tests for CLI exit code mapping."""

from __future__ import annotations

import builtins
import sys
from types import SimpleNamespace

import pytest

from resonance.errors import IOFailure, RuntimeFailure, ValidationError


def test_cli_maps_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from resonance import cli

    def raise_validation(_args, **_kwargs):
        raise ValidationError("bad input")

    monkeypatch.setattr("resonance.commands.apply.run_apply", raise_validation)
    monkeypatch.setattr(sys, "argv", ["resonance", "apply", "--plan", "p", "--state-db", "s"])
    assert cli.main() == ValidationError.exit_code


def test_cli_maps_io_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from resonance import cli

    def raise_io(_args, **_kwargs):
        raise OSError("disk error")

    monkeypatch.setattr("resonance.commands.scan.run_scan", raise_io)
    monkeypatch.setattr(sys, "argv", ["resonance", "scan", "path"])
    assert cli.main() == IOFailure.exit_code


def test_cli_maps_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from resonance import cli

    def raise_runtime(_args, **_kwargs):
        raise RuntimeFailure("boom")

    monkeypatch.setattr("resonance.commands.prescan.run_prescan", raise_runtime)
    monkeypatch.setattr(sys, "argv", ["resonance", "prescan", "path"])
    assert cli.main() == RuntimeFailure.exit_code
