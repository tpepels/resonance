"""Unit tests for auto_probable settings fields."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from resonance.settings import Settings, load_settings, settings_hash


def test_settings_auto_probable_defaults() -> None:
    s = Settings()
    assert s.auto_probable is False
    assert s.auto_probable_min_gap == 0.15


def test_load_settings_auto_probable_from_json(tmp_path: Path) -> None:
    config = tmp_path / "settings.json"
    config.write_text(json.dumps({"auto_probable": True, "auto_probable_min_gap": 0.20}))
    s = load_settings(config)
    assert s.auto_probable is True
    assert s.auto_probable_min_gap == 0.20


def test_load_settings_auto_probable_defaults_when_absent(tmp_path: Path) -> None:
    config = tmp_path / "settings.json"
    config.write_text(json.dumps({}))
    s = load_settings(config)
    assert s.auto_probable is False
    assert s.auto_probable_min_gap == 0.15


def test_settings_hash_resolve_stage() -> None:
    s1 = Settings(auto_probable=False)
    s2 = Settings(auto_probable=True)
    assert settings_hash(s1, "resolve") != settings_hash(s2, "resolve")


def test_settings_hash_resolve_ignores_backend() -> None:
    s1 = Settings(tag_writer_backend="meta-json", auto_probable=True)
    s2 = Settings(tag_writer_backend="mutagen", auto_probable=True)
    assert settings_hash(s1, "resolve") == settings_hash(s2, "resolve")
