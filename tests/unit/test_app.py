"""Unit tests for ResonanceApp legacy gating."""

from __future__ import annotations

from pathlib import Path

import pytest

from resonance.app import ResonanceApp


def test_create_pipeline_requires_legacy_flag(tmp_path: Path) -> None:
    app = ResonanceApp(
        library_root=tmp_path,
        cache_path=tmp_path / "cache.db",
        interactive=False,
        dry_run=True,
    )
    try:
        with pytest.raises(ValueError, match="V2 visitor pipeline is deprecated"):
            app.create_pipeline()
    finally:
        app.close()
