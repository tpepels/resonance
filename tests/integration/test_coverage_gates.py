"""Coverage gate tests for V3.05 governance compliance.

These tests ensure > 0% coverage for hard wiring gates required by GOVERNANCE.md §4.1.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from resonance.core.identifier import DirectoryEvidence, TrackEvidence
from resonance.core.state import DirectoryState
from resonance.infrastructure.directory_store import DirectoryStateStore
from resonance.providers.acoustid import AcoustIDClient


def test_app_bootstrap_smoke(tmp_path: Path) -> None:
    """Smoke test for resonance/app.py - basic bootstrap coverage."""
    from resonance.app import ResonanceApp

    # Create minimal app instance
    app = ResonanceApp(
        library_root=tmp_path / "library",
        cache_path=tmp_path / "cache.db",
        offline=True,  # Avoid network calls
    )

    # Verify basic initialization
    assert app.library_root == tmp_path / "library"
    assert app.cache_path == tmp_path / "cache.db"
    assert app.offline is True

    # Clean up
    app.close()


def test_app_from_env_smoke(tmp_path: Path) -> None:
    """Smoke test for ResonanceApp.from_env() method."""
    from resonance.app import ResonanceApp

    # Test from_env class method
    app = ResonanceApp.from_env(
        library_root=tmp_path / "library",
        cache_path=tmp_path / "cache.db",
        offline=True,
    )

    assert app.library_root == tmp_path / "library"
    assert app.cache_path == tmp_path / "cache.db"
    assert app.offline is True

    app.close()


def test_identify_command_smoke(tmp_path: Path) -> None:
    """Smoke test for resonance/commands/identify.py - basic command execution."""
    from argparse import Namespace
    from resonance.commands.identify import run_identify

    # Create a mock directory with audio files
    audio_dir = tmp_path / "album"
    audio_dir.mkdir()

    # Create a fake audio file
    audio_file = audio_dir / "track.flac"
    audio_file.write_text("fake audio")
    meta_file = audio_file.with_suffix(audio_file.suffix + ".meta.json")
    meta_file.write_text('{"fingerprint_id": "fp-123", "duration_seconds": 180}')

    # Create mock args
    args = Namespace(directory=str(audio_dir), json=False)

    # Create mock provider that properly implements ProviderClient
    from resonance.core.identifier import ProviderCapabilities

    class MockProvider:
        @property
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(supports_fingerprints=True, supports_metadata=True)

        def search_by_fingerprints(self, fingerprints):
            return []

        def search_by_metadata(self, artist, album, track_count):
            return []

    mock_provider = MockProvider()

    # Mock evidence builder
    def mock_evidence_builder(files, fingerprint_reader=None):
        return DirectoryEvidence(
            tracks=(TrackEvidence(fingerprint_id="fp-123", duration_seconds=180),),
            track_count=1,
            total_duration_seconds=180,
        )

    # Capture output
    output_lines = []
    def capture_output(line: str) -> None:
        output_lines.append(line)

    # Run identify command
    exit_code = run_identify(
        args,
        provider_client=mock_provider,
        evidence_builder=mock_evidence_builder,
        output_sink=capture_output,
    )

    # Verify it ran without error
    assert exit_code == 0
    assert len(output_lines) > 0


def test_unjail_command_smoke(tmp_path: Path) -> None:
    """Smoke test for resonance/commands/unjail.py - basic command execution."""
    from resonance.commands.unjail import run_unjail
    from resonance.infrastructure.directory_store import DirectoryStateStore

    # Create a store and add a jailed directory
    store = DirectoryStateStore(tmp_path / "state.db")

    # Add and jail a directory (use proper 64-char hex hash)
    signature_hash = "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
    record = store.get_or_create("test-dir", tmp_path / "test", signature_hash)
    store.set_state("test-dir", DirectoryState.JAILED)

    # Verify it's jailed
    jailed_record = store.get("test-dir")
    assert jailed_record is not None
    assert jailed_record.state == DirectoryState.JAILED

    # Run unjail command
    result = run_unjail(store=store, dir_id="test-dir")

    # Verify unjail worked - returns the updated DirectoryRecord
    assert result is not None
    assert result.state == DirectoryState.NEW
    assert result.dir_id == "test-dir"

    store.close()


def test_env_file_loading(tmp_path: Path) -> None:
    """Test that .env files are loaded automatically (when python-dotenv is available)."""
    # Create a test .env file
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_ACOUSTID_KEY=loaded-from-env\n")

    # Change to the temp directory to test .env loading
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        # Import and call the dotenv loader
        from resonance.cli import _load_dotenv_files
        _load_dotenv_files()

        # Check if the environment variable was loaded (only if dotenv is available)
        try:
            import dotenv
            assert os.getenv("TEST_ACOUSTID_KEY") == "loaded-from-env"
        except ImportError:
            # python-dotenv not installed, skip the assertion
            pytest.skip("python-dotenv not installed")

    finally:
        os.chdir(original_cwd)


def test_acoustid_client_env_loading() -> None:
    """Test that AcoustID client loads API key from environment."""
    # Set environment variable
    os.environ["ACOUSTID_API_KEY"] = "test-key-from-env"

    try:
        # Create client without explicit key - should load from env
        client = AcoustIDClient()

        # Verify it loaded the key from environment
        assert client.api_key == "test-key-from-env"

    finally:
        # Clean up
        del os.environ["ACOUSTID_API_KEY"]


def test_acoustid_client_explicit_key_overrides_env() -> None:
    """Test that explicit API key overrides environment variable."""
    # Set environment variable
    os.environ["ACOUSTID_API_KEY"] = "env-key"

    try:
        # Create client with explicit key - should override env
        client = AcoustIDClient(api_key="explicit-key")

        # Verify explicit key takes precedence
        assert client.api_key == "explicit-key"

    finally:
        # Clean up
        del os.environ["ACOUSTID_API_KEY"]
