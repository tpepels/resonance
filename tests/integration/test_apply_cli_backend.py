"""Integration tests for apply CLI backend resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resonance.settings import load_settings, resolve_tag_writer_backend


def test_apply_cli_backend_overrides_env_and_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"tag_writer_backend": "meta-json"}))
    monkeypatch.setenv("RESONANCE_TAG_WRITER_BACKEND", "mutagen")

    settings = load_settings(config_path)
    import os
    backend = resolve_tag_writer_backend(
        cli_backend="meta-json",
        env_backend=os.getenv("RESONANCE_TAG_WRITER_BACKEND"),
        config_backend=settings.tag_writer_backend,
    )
    assert backend == "meta-json"


def test_apply_env_overrides_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"tag_writer_backend": "meta-json"}))
    monkeypatch.setenv("RESONANCE_TAG_WRITER_BACKEND", "mutagen")

    settings = load_settings(config_path)
    import os
    backend = resolve_tag_writer_backend(
        cli_backend=None,
        env_backend=os.getenv("RESONANCE_TAG_WRITER_BACKEND"),
        config_backend=settings.tag_writer_backend,
    )
    assert backend == "mutagen"


def test_apply_config_used_when_no_cli_or_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"tag_writer_backend": "mutagen"}))
    monkeypatch.delenv("RESONANCE_TAG_WRITER_BACKEND", raising=False)

    settings = load_settings(config_path)
    import os
    backend = resolve_tag_writer_backend(
        cli_backend=None,
        env_backend=os.getenv("RESONANCE_TAG_WRITER_BACKEND"),
        config_backend=settings.tag_writer_backend,
    )
    assert backend == "mutagen"


def test_apply_rejects_unknown_backend(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"tag_writer_backend": "nope"}))

    with pytest.raises(ValueError, match="Unsupported tag writer backend"):
        load_settings(config_path)
