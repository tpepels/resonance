"""Pytest configuration and shared fixtures for integration tests."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator, Any
from unittest.mock import Mock, patch

import pytest

from tests.helpers.scenarios import build_golden_scenario, GoldenScenario
from tests.helpers.fs import AudioStubSpec, build_album_dir, AlbumFixture


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
def mock_app_no_network(test_cache: Path, test_library: Path):
    """Create a ResonanceApp with mocked network calls."""
    from resonance.app import ResonanceApp

    # Mock the MusicBrainz and Discogs clients to avoid network calls
    with patch("resonance.app.MusicBrainzClient"), \
         patch("resonance.app.DiscogsClient"):

        app = ResonanceApp.from_env(
            library_root=test_library,
            cache_path=test_cache,
            interactive=False,  # Non-interactive for tests
            dry_run=False,
        )

        yield app

        # Cleanup
        app.close()


class TestScenario:
    """Helper class for defining test scenarios."""

    def __init__(
        self,
        name: str,
        description: str,
        input_files: list[dict[str, Any]],
        expected_output: dict[str, Any],
        mock_responses: dict[str, Any] | None = None,
    ):
        """Initialize test scenario.

        Args:
            name: Scenario name
            description: Human-readable description
            input_files: List of input file specs
            expected_output: Expected outcome (paths, metadata, etc.)
            mock_responses: Mock API responses to use
        """
        self.name = name
        self.description = description
        self.input_files = input_files
        self.expected_output = expected_output
        self.mock_responses = mock_responses or {}

    def setup(self, base_dir: Path, create_file_fn) -> Path:
        """Create test files in base_dir.

        Args:
            base_dir: Base directory for test files
            create_file_fn: Function to create audio files

        Returns:
            Path to input directory
        """
        input_dir = base_dir / "input" / self.name
        input_dir.mkdir(parents=True, exist_ok=True)

        for file_spec in self.input_files:
            file_path = input_dir / file_spec["filename"]
            create_file_fn(
                path=file_path,
                title=file_spec.get("title"),
                artist=file_spec.get("artist"),
                album=file_spec.get("album"),
                track_number=file_spec.get("track_number"),
                duration=file_spec.get("duration", 180),
            )

        return input_dir


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


@pytest.fixture
def getz_gilberto_scenario(mock_musicbrainz_response, mock_acoustid_response):
    """Test scenario: Getz/Gilberto with artist name variants."""

    # Mock MusicBrainz release
    mb_response = mock_musicbrainz_response(
        release_id="c4f86c97-d672-33d0-8f2c-a0a5bfdb2a7e",
        album_title="Getz/Gilberto",
        album_artist="Stan Getz & João Gilberto",
        release_date="1964-03",
        tracks=[
            {"title": "The Girl from Ipanema", "duration": 326},
            {"title": "Doralice", "duration": 157},
            {"title": "P'ra Machucar Meu Coração", "duration": 251},
        ],
    )

    return TestScenario(
        name="getz_gilberto",
        description="Multi-artist album with name variants",
        input_files=[
            {
                "filename": "01 - The Girl from Ipanema.flac",
                "title": "The Girl from Ipanema",
                "artist": "Stan Getz & João Gilberto",  # Variant 1
                "album": "Getz/Gilberto",
                "track_number": 1,
                "duration": 326,
            },
            {
                "filename": "02 - Doralice.flac",
                "title": "Doralice",
                "artist": "Getz, Gilberto",  # Variant 2
                "album": "Getz/Gilberto",
                "track_number": 2,
                "duration": 157,
            },
            {
                "filename": "03 - P'ra Machucar Meu Coração.flac",
                "title": "P'ra Machucar Meu Coração",
                "artist": "Getz/Gilberto",  # Variant 3
                "album": "Getz-Gilberto",  # Slight album variant
                "track_number": 3,
                "duration": 251,
            },
        ],
        expected_output={
            "canonical_artist": "Stan Getz & João Gilberto",  # Canonical form
            "canonical_album": "Getz/Gilberto",
            "release_id": "c4f86c97-d672-33d0-8f2c-a0a5bfdb2a7e",
            "provider": "musicbrainz",
            "output_path_pattern": r"Stan Getz.*João Gilberto/Getz.*Gilberto",
            "track_count": 3,
        },
        mock_responses={
            "musicbrainz": mb_response,
        },
    )


# More scenario fixtures will be added here...
