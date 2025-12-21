"""Integration tests for CLI exit code mapping."""

from __future__ import annotations

import builtins
import sys
from types import SimpleNamespace

import pytest

from resonance.errors import IOFailure, RuntimeFailure, ValidationError


def test_cli_maps_validation_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from resonance import cli

    def raise_validation(_args, **_kwargs):
        raise ValidationError("bad input")

    monkeypatch.setattr("resonance.commands.apply.run_apply", raise_validation)
    state_db = tmp_path / "state.db"
    monkeypatch.setattr(sys, "argv", ["resonance", "apply", "--plan", "p", "--state-db", str(state_db)])
    assert cli.main() == ValidationError.exit_code


def test_cli_maps_io_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from resonance import cli

    def raise_io(_args, **_kwargs):
        raise OSError("disk error")

    monkeypatch.setattr("resonance.commands.apply.run_apply", raise_io)
    state_db = tmp_path / "state.db"
    monkeypatch.setattr(sys, "argv", ["resonance", "apply", "--plan", "p", "--state-db", str(state_db)])
    assert cli.main() == IOFailure.exit_code


def test_cli_maps_runtime_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from resonance import cli

    def raise_runtime(_args, **_kwargs):
        raise RuntimeFailure("boom")

    monkeypatch.setattr("resonance.commands.plan.run_plan", raise_runtime)
    state_db = tmp_path / "state.db"
    monkeypatch.setattr(sys, "argv", ["resonance", "plan", "--dir-id", "d", "--state-db", str(state_db)])
    assert cli.main() == RuntimeFailure.exit_code
