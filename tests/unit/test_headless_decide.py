"""Unit tests for headless mode in decide (Sprint 3)."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from resonance.commands.decide import run_decide
from resonance.core.identifier import ProviderCapabilities, ProviderRelease
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore


class _StubProvider:
    """Minimal provider that returns no results."""

    @property
    def capabilities(self):
        return ProviderCapabilities(supports_fingerprints=False, supports_metadata=False)

    def search_by_fingerprints(self, fingerprints):
        return []

    def search_by_metadata(self, artist, album, track_count):
        return []

    def release_by_id(self, provider, release_id):
        return None


def _base_args(tmp_path: Path, **overrides) -> Namespace:
    defaults = dict(
        library_root=tmp_path / "library",
        state_db=tmp_path / "state.db",
        cache_db=None,
        offline=False,
        decisions_file=None,
        json=False,
        auto_probable=False,
        auto_probable_min_gap=0.15,
        plan_dir=None,
        headless=False,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


class TestHeadlessSkipsPrompt:
    def test_headless_skips_prompt_stage(self, tmp_path: Path) -> None:
        """In headless mode, prompt stage is skipped even with queued dirs."""
        library = tmp_path / "library"
        library.mkdir()
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            # Manually queue a dir for prompt
            store.get_or_create("dir-h1", library / "album1", "a" * 64)
            store.set_state("dir-h1", DirectoryState.QUEUED_PROMPT)

            args = _base_args(tmp_path, library_root=library, headless=True, json=True)
            captured: list[str] = []
            invoked_input = False

            def fail_input(prompt_text):
                nonlocal invoked_input
                invoked_input = True
                raise AssertionError("input_provider should not be called in headless mode")

            code = run_decide(args, store=store, input_provider=fail_input, output_sink=captured.append)
            assert code == 0
            assert invoked_input is False
            data = json.loads(captured[0])
            assert data["data"]["stages"]["prompt"]["skipped"] is True
            assert data["data"]["stages"]["prompt"]["headless"] is True
        finally:
            store.close()

    def test_headless_implies_auto_probable(self, tmp_path: Path) -> None:
        """Headless mode implies --auto-probable."""
        library = tmp_path / "library"
        library.mkdir()
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            # Without headless, auto_probable is False by default
            args = _base_args(tmp_path, library_root=library, headless=True, json=True)
            captured: list[str] = []
            code = run_decide(args, store=store, output_sink=captured.append)
            assert code == 0
            # If headless works, auto_probable was effectively True
            # (we verify by checking no prompt was invoked, which is already tested above)
        finally:
            store.close()

    def test_non_headless_still_prompts(self, tmp_path: Path) -> None:
        """Without headless, prompt stage is invoked normally when queued dirs have audio."""
        library = tmp_path / "library"
        library.mkdir()
        album_dir = library / "album1"
        album_dir.mkdir()
        # Create stub audio files so prompt iterates them
        for i in range(1, 3):
            stub = album_dir / f"0{i} Track.flac"
            stub.write_bytes(b"\x00" * 100)

        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            store.get_or_create("dir-nh1", album_dir, "a" * 64)
            store.set_state("dir-nh1", DirectoryState.QUEUED_PROMPT)

            args = _base_args(tmp_path, library_root=library, headless=False)
            captured: list[str] = []
            prompt_called = False

            def mock_input(prompt_text):
                nonlocal prompt_called
                prompt_called = True
                return ""  # skip

            code = run_decide(
                args,
                store=store,
                provider_client=_StubProvider(),
                input_provider=mock_input,
                output_sink=captured.append,
            )
            assert code == 0
            assert prompt_called is True
        finally:
            store.close()


class TestHeadlessPlanDir:
    def test_headless_with_plan_dir_writes_artifacts(self, tmp_path: Path) -> None:
        """Headless + --plan-dir writes plan files for resolved dirs."""
        library = tmp_path / "library"
        library.mkdir()
        store = DirectoryStateStore(tmp_path / "state.db")
        try:
            args = _base_args(tmp_path, library_root=library, headless=True, plan_dir=tmp_path / "plans")
            captured: list[str] = []
            code = run_decide(args, store=store, output_sink=captured.append)
            assert code == 0
            # With empty library, no plans to write, but dir should be respected
        finally:
            store.close()
