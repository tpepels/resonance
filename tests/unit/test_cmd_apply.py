"""Unit tests for apply command."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from resonance.commands.apply import run_apply
from resonance.errors import ValidationError
from resonance.settings import Settings


def _stub_config_loader(path):
    """Return default settings without touching filesystem."""
    return Settings()


def _base_args(**overrides) -> Namespace:
    defaults = dict(
        config=None,
        tag_writer_backend=None,
        plan=None,
        state_db=None,
        library_root=None,
        tag_patch=None,
        no_dry_run=False,
        json=False,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


class TestRunApply:
    def test_not_implemented_when_apply_fn_none(self) -> None:
        captured: list[str] = []
        code = run_apply(
            _base_args(),
            apply_fn=None,
            config_loader=_stub_config_loader,
            output_sink=captured.append,
        )
        assert code == 1

    def test_raises_without_plan(self) -> None:
        with pytest.raises(ValidationError, match="--plan"):
            run_apply(
                _base_args(plan=None),
                config_loader=_stub_config_loader,
            )

    def test_raises_without_state_db(self) -> None:
        with pytest.raises(ValidationError, match="--state-db"):
            run_apply(
                _base_args(plan="/some/plan.json", state_db=None),
                config_loader=_stub_config_loader,
            )

    def test_raises_without_store(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="store is required"):
            run_apply(
                _base_args(plan="/p.json", state_db="/s.db", library_root=str(tmp_path)),
                config_loader=_stub_config_loader,
                store=None,
            )

    def test_custom_apply_fn_receives_writer(self) -> None:
        received = {}

        def fake_apply(tag_writer, backend):
            received["backend"] = backend
            return None

        captured: list[str] = []
        code = run_apply(
            _base_args(plan="/p.json", state_db="/s.db"),
            apply_fn=fake_apply,
            config_loader=_stub_config_loader,
            output_sink=captured.append,
        )
        assert code == 0
        assert received["backend"] == "meta-json"

    def test_plan_load_error_returns_1(self, tmp_path: Path) -> None:
        from resonance.infrastructure.directory_store import DirectoryStateStore

        store = DirectoryStateStore(tmp_path / "state.db")
        captured: list[str] = []
        try:
            code = run_apply(
                _base_args(
                    plan=str(tmp_path / "nonexistent.json"),
                    state_db=str(tmp_path / "state.db"),
                    library_root=str(tmp_path),
                ),
                config_loader=_stub_config_loader,
                store=store,
                output_sink=captured.append,
            )
        finally:
            store.close()
        assert code == 1
