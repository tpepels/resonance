"""Tests for API invocation policy boundaries."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from resonance.api.context import InvocationContext, InvocationMode
from resonance.api.service import ResonanceService
from resonance.errors import ValidationError


def test_prompt_requires_scripted_input_in_automation_mode(tmp_path: Path) -> None:
    service = ResonanceService()
    args = Namespace(
        command="prompt",
        state_db=tmp_path / "state.db",
        cache_db=None,
        decisions_file=None,
        record_replay=None,
        replay_file=None,
        json=False,
        mode="automation",
    )

    with pytest.raises(ValidationError, match="prompt requires --decisions-file or --replay-file"):
        service.execute_namespace(
            args,
            context=InvocationContext(mode=InvocationMode.AUTOMATION),
        )


def test_prompt_allowed_with_decisions_file_in_automation_mode(tmp_path: Path) -> None:
    service = ResonanceService()
    decisions_file = tmp_path / "decisions.json"
    decisions_file.write_text("{}", encoding="utf-8")

    args = Namespace(
        command="prompt",
        state_db=tmp_path / "state.db",
        cache_db=None,
        decisions_file=decisions_file,
        record_replay=None,
        replay_file=None,
        json=False,
        mode="automation",
    )

    code = service.execute_namespace(
        args,
        context=InvocationContext(mode=InvocationMode.AUTOMATION),
    )
    assert isinstance(code, int)
