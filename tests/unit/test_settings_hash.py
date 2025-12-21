"""Unit tests for settings_hash relevance sets."""

from __future__ import annotations

import pytest

from resonance.settings import Settings, settings_hash


def test_settings_hash_identify_ignores_irrelevant_fields() -> None:
    base = Settings(tag_writer_backend="meta-json", identify_scoring_version="v1")
    changed = Settings(tag_writer_backend="mutagen", identify_scoring_version="v1")
    assert settings_hash(base, "identify") == settings_hash(changed, "identify")


def test_settings_hash_identify_changes_on_relevant_field() -> None:
    base = Settings(identify_scoring_version="v1")
    changed = Settings(identify_scoring_version="v2")
    assert settings_hash(base, "identify") != settings_hash(changed, "identify")


def test_settings_hash_plan_changes_on_relevant_field() -> None:
    base = Settings(plan_conflict_policy="FAIL")
    changed = Settings(plan_conflict_policy="RENAME")
    assert settings_hash(base, "plan") != settings_hash(changed, "plan")


def test_settings_hash_plan_ignores_identify_field() -> None:
    base = Settings(plan_conflict_policy="FAIL", identify_scoring_version="v1")
    changed = Settings(plan_conflict_policy="FAIL", identify_scoring_version="v2")
    assert settings_hash(base, "plan") == settings_hash(changed, "plan")


def test_settings_hash_rejects_unknown_stage() -> None:
    with pytest.raises(ValueError, match="Unknown settings hash stage"):
        settings_hash(Settings(), "unknown")
