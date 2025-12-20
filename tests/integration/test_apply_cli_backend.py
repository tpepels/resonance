"""Integration tests for apply CLI backend resolution."""

from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path

import pytest

from resonance.commands.apply import run_apply


def test_apply_cli_backend_overrides_env_and_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"tag_writer_backend": "meta-json"}))
    monkeypatch.setenv("RESONANCE_TAG_WRITER_BACKEND", "mutagen")

    seen = {}

    def apply_fn(*_args, **kwargs):
        seen.update(kwargs)

    args = Namespace(
        config=config_path,
        tag_writer_backend="meta-json",
        plan=tmp_path / "plan.json",
        state_db=tmp_path / "state.db",
    )
    run_apply(args, apply_fn=apply_fn)
    assert seen["backend"] == "meta-json"


def test_apply_env_overrides_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"tag_writer_backend": "meta-json"}))
    monkeypatch.setenv("RESONANCE_TAG_WRITER_BACKEND", "mutagen")

    seen = {}

    def apply_fn(*_args, **kwargs):
        seen.update(kwargs)

    args = Namespace(
        config=config_path,
        tag_writer_backend=None,
        plan=tmp_path / "plan.json",
        state_db=tmp_path / "state.db",
    )
    run_apply(args, apply_fn=apply_fn)
    assert seen["backend"] == "mutagen"


def test_apply_config_used_when_no_cli_or_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"tag_writer_backend": "mutagen"}))
    monkeypatch.delenv("RESONANCE_TAG_WRITER_BACKEND", raising=False)

    seen = {}

    def apply_fn(*_args, **kwargs):
        seen.update(kwargs)

    args = Namespace(
        config=config_path,
        tag_writer_backend=None,
        plan=tmp_path / "plan.json",
        state_db=tmp_path / "state.db",
    )
    run_apply(args, apply_fn=apply_fn)
    assert seen["backend"] == "mutagen"
    assert seen["tag_writer"] is not None


def test_apply_rejects_unknown_backend(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"tag_writer_backend": "nope"}))

    args = Namespace(
        config=config_path,
        tag_writer_backend=None,
        plan=tmp_path / "plan.json",
        state_db=tmp_path / "state.db",
    )
    with pytest.raises(ValueError, match="Unsupported tag writer backend"):
        run_apply(args, apply_fn=lambda **_: None)
