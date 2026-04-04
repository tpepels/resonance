"""Pytest configuration and shared fixtures for integration tests."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator, Any

import pytest

from tests.helpers.scenarios import build_golden_scenario, GoldenScenario
from tests.helpers.fs import AudioStubSpec, build_album_dir, AlbumFixture

collect_ignore_glob = ["archived/*"]


_PIPELINE_V1_PATHS = (
    "tests/test_visitors/",
    "tests/test_services/",
    "tests/integration/test_classical.py",
    "tests/integration/test_multi_artist.py",
    "tests/integration/test_name_variants.py",
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_network = os.getenv("RUN_REQUIRES_NETWORK", "").lower() in {"1", "true", "yes"}
    run_slow = os.getenv("RUN_SLOW", "").lower() in {"1", "true", "yes"}
    for item in items:
        path = str(item.fspath).replace("\\", "/")
        if any(token in path for token in _PIPELINE_V1_PATHS):
            item.add_marker(pytest.mark.pipeline_v1)
        else:
            item.add_marker(pytest.mark.pipeline_v2)
        if "requires_network" in item.keywords and not run_network:
            item.add_marker(pytest.mark.skip(reason="requires network access"))
        if "slow" in item.keywords and not run_slow:
            item.add_marker(pytest.mark.skip(reason="slow test"))

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    tmpdir = Path(tempfile.mkdtemp())
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def test_cache(temp_dir: Path) -> Path:
    """Create a temporary cache database."""
    cache_path = temp_dir / "test_cache.db"
    return cache_path


@pytest.fixture
def test_library(temp_dir: Path) -> Path:
    """Create a temporary library directory."""
    library = temp_dir / "library"
    library.mkdir()
    return library


@pytest.fixture
def test_output(temp_dir: Path) -> Path:
    """Create a temporary output directory."""
    output = temp_dir / "output"
    output.mkdir()
    return output


@pytest.fixture
def mock_musicbrainz_response():
    """Factory for creating mock MusicBrainz API responses."""
    def _create_response(
        release_id: str,
        album_title: str,
        album_artist: str,
        tracks: list[dict[str, Any]],
        release_date: str | None = None,
    ) -> dict[str, Any]:
        """Create a mock MusicBrainz release response.

        Args:
            release_id: MusicBrainz release ID
            album_title: Album title
            album_artist: Album artist name
            tracks: List of track dicts with 'title', 'artist', 'duration'
            release_date: Release date (YYYY-MM-DD)

        Returns:
            Dict matching MusicBrainz API response structure
        """
        return {
            "id": release_id,
            "title": album_title,
            "artist-credit": [{"name": album_artist}],
            "date": release_date,
            "media": [
                {
                    "tracks": [
                        {
                            "id": f"track-{i}",
                            "title": track["title"],
                            "length": track.get("duration", 0) * 1000,  # Convert to ms
                            "artist-credit": [{"name": track.get("artist", album_artist)}],
                            "position": i + 1,
                        }
                        for i, track in enumerate(tracks)
                    ]
                }
            ],
        }
    return _create_response


@pytest.fixture
def mock_acoustid_response():
    """Factory for creating mock AcoustID API responses."""
    def _create_response(
        fingerprint: str,
        duration: int,
        recordings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create a mock AcoustID lookup response.

        Args:
            fingerprint: Audio fingerprint
            duration: Track duration in seconds
            recordings: List of recording matches with 'id', 'title', 'artists', 'releases'

        Returns:
            Dict matching AcoustID API response structure
        """
        return {
            "status": "ok",
            "results": [
                {
                    "score": 1.0,
                    "recordings": [
                        {
                            "id": rec["id"],
                            "title": rec["title"],
                            "artists": [{"name": a} for a in rec.get("artists", [])],
                            "releases": [
                                {
                                    "id": rel["id"],
                                    "title": rel.get("title", ""),
                                    "country": rel.get("country", "US"),
                                }
                                for rel in rec.get("releases", [])
                            ],
                        }
                        for rec in recordings
                    ],
                }
            ],
        }
    return _create_response


@pytest.fixture
def create_test_audio_file(temp_dir: Path):
    """Factory for creating test audio files with metadata.

    Note: Creates minimal valid audio files for testing.
    For real fingerprinting tests, use actual audio samples.
    """
    def _create_file(
        path: Path,
        title: str | None = None,
        artist: str | None = None,
        album: str | None = None,
        track_number: int | None = None,
        disc_number: int | None = None,
        duration: int = 180,  # seconds
        composer: str | None = None,
        conductor: str | None = None,
        performer: str | None = None,
    ) -> Path:
        """Create a test audio file.

        Args:
            path: Output file path (should end in .mp3, .flac, etc.)
            title: Track title
            artist: Artist name
            album: Album name
            track_number: Track number
            duration: Duration in seconds

        Returns:
            Path to created file
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        # For now, create an empty file
        # In real tests, we'd create actual audio with mutagen
        path.touch()

        # Store metadata in companion JSON for test validation
        metadata_path = path.with_suffix(path.suffix + ".meta.json")
        # Generate a deterministic fingerprint for testing
        fingerprint = f"fp-{hash((title or '', artist or '', album or '', track_number or 0, disc_number or 1)) % 1000000:06d}"
        metadata = {
            "title": title,
            "artist": artist,
            "album": album,
            "track_number": track_number,
            "disc_number": disc_number,
            "duration": duration,
            "composer": composer,
            "conductor": conductor,
            "performer": performer,
            "fingerprint": fingerprint,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2))

        return path

    return _create_file


@pytest.fixture
def album_dir_factory(temp_dir: Path):
    """Factory for creating album directories with audio/non-audio stubs."""
    def _create_album(
        name: str,
        audio_specs: list[AudioStubSpec],
        non_audio_files: list[str] | None = None,
    ) -> AlbumFixture:
        return build_album_dir(temp_dir / "albums", name, audio_specs, non_audio_files)

    return _create_album


@pytest.fixture
def golden_scenario_builder(temp_dir: Path):
    """Factory for building golden scenario fixtures."""
    def _build(name: str) -> GoldenScenario:
        return build_golden_scenario(temp_dir, name)

    return _build


@pytest.fixture
def pop_certain(golden_scenario_builder) -> GoldenScenario:
    return golden_scenario_builder("pop_certain")


@pytest.fixture
def pop_probable(golden_scenario_builder) -> GoldenScenario:
    return golden_scenario_builder("pop_probable")


@pytest.fixture
def compilation(golden_scenario_builder) -> GoldenScenario:
    return golden_scenario_builder("compilation")


@pytest.fixture
def classical_single_composer(golden_scenario_builder) -> GoldenScenario:
    return golden_scenario_builder("classical_single_composer")


@pytest.fixture
def classical_mixed_composer(golden_scenario_builder) -> GoldenScenario:
    return golden_scenario_builder("classical_mixed_composer")


@pytest.fixture
def mixed_release_in_one_dir(golden_scenario_builder) -> GoldenScenario:
    return golden_scenario_builder("mixed_release_in_one_dir")


@pytest.fixture
def non_audio_present(golden_scenario_builder) -> GoldenScenario:
    return golden_scenario_builder("non_audio_present")


@pytest.fixture
def target_exists_conflict(golden_scenario_builder) -> GoldenScenario:
    return golden_scenario_builder("target_exists_conflict")
