"""Unit tests for deterministic settings defaults."""

from __future__ import annotations

import os
from pathlib import Path

from resonance.settings import default_config_path


def test_default_config_path_is_deterministic(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/tmp/resonance-home")
    assert default_config_path() == Path(
        "/tmp/resonance-home/.config/resonance/settings.json"
    )
