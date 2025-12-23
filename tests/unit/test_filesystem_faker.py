"""Unit tests for FilesystemFaker."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from tests.integration._filesystem_faker import FilesystemFaker, FakerContext, create_faker_for_corpus


class TestFilesystemFaker:
    """Test FilesystemFaker functionality."""

    def test_faker_initialization_with_valid_metadata(self, tmp_path: Path) -> None:
        """Test faker initializes correctly with valid metadata."""
        # Create test metadata
        metadata = {
            "files": [
                {
                    "path": "album/track1.flac",
                    "size": 12345,
                    "mtime": 1609459200,
                    "permissions": "644",
                    "is_audio": True,
                    "audio_info": {"duration": 180}
                },
                {
                    "path": "album/track2.mp3",
                    "size": 9876,
                    "mtime": 1609459201,
                    "permissions": "755",
                    "is_audio": True,
                    "audio_info": {"duration": 200}
                }
            ]
        }

        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        # Verify metadata was loaded
        assert len(faker._file_index) == 2
        assert "album/track1.flac" in faker._file_index
        assert "album/track2.mp3" in faker._file_index

    def test_faker_initialization_missing_metadata_file(self, tmp_path: Path) -> None:
        """Test faker raises error for missing metadata file."""
        missing_file = tmp_path / "missing.json"

        with pytest.raises(FileNotFoundError, match="Metadata file not found"):
            FilesystemFaker(missing_file)

    def test_exists_file(self, tmp_path: Path) -> None:
        """Test exists() returns True for files."""
        metadata = {"files": [{"path": "test.txt", "size": 100, "mtime": 1234567890, "permissions": "644", "is_audio": False, "audio_info": {}}]}
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        assert faker.exists("test.txt") is True
        assert faker.exists("nonexistent.txt") is False

    def test_exists_directory(self, tmp_path: Path) -> None:
        """Test exists() returns True for directories."""
        metadata = {"files": [{"path": "album/track.flac", "size": 100, "mtime": 1234567890, "permissions": "644", "is_audio": True, "audio_info": {}}]}
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        assert faker.exists("album") is True  # Directory exists
        assert faker.exists("album/track.flac") is True  # File exists
        assert faker.exists("nonexistent") is False

    def test_isfile(self, tmp_path: Path) -> None:
        """Test isfile() correctly identifies files."""
        metadata = {"files": [{"path": "test.txt", "size": 100, "mtime": 1234567890, "permissions": "644", "is_audio": False, "audio_info": {}}]}
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        assert faker.isfile("test.txt") is True
        assert faker.isfile("nonexistent.txt") is False

    def test_isdir(self, tmp_path: Path) -> None:
        """Test isdir() correctly identifies directories."""
        metadata = {"files": [{"path": "album/track.flac", "size": 100, "mtime": 1234567890, "permissions": "644", "is_audio": True, "audio_info": {}}]}
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        assert faker.isdir("album") is True
        assert faker.isdir("nonexistent") is False
        assert faker.isdir("album/track.flac") is False  # File, not directory

    def test_getsize(self, tmp_path: Path) -> None:
        """Test getsize() returns correct file sizes."""
        metadata = {"files": [{"path": "test.txt", "size": 12345, "mtime": 1234567890, "permissions": "644", "is_audio": False, "audio_info": {}}]}
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        assert faker.getsize("test.txt") == 12345

        with pytest.raises(FileNotFoundError):
            faker.getsize("nonexistent.txt")

    def test_getmtime(self, tmp_path: Path) -> None:
        """Test getmtime() returns correct modification times."""
        metadata = {"files": [{"path": "test.txt", "size": 100, "mtime": 1234567890, "permissions": "644", "is_audio": False, "audio_info": {}}]}
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        assert faker.getmtime("test.txt") == 1234567890.0

        with pytest.raises(FileNotFoundError):
            faker.getmtime("nonexistent.txt")

    def test_listdir_root(self, tmp_path: Path) -> None:
        """Test listdir() at root level."""
        metadata = {
            "files": [
                {"path": "track1.flac", "size": 100, "mtime": 1234567890, "permissions": "644", "is_audio": True, "audio_info": {}},
                {"path": "track2.mp3", "size": 200, "mtime": 1234567891, "permissions": "644", "is_audio": True, "audio_info": {}}
            ]
        }
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        items = faker.listdir(".")
        assert items == ["track1.flac", "track2.mp3"]

    def test_listdir_subdirectory(self, tmp_path: Path) -> None:
        """Test listdir() in subdirectories."""
        metadata = {
            "files": [
                {"path": "album/track1.flac", "size": 100, "mtime": 1234567890, "permissions": "644", "is_audio": True, "audio_info": {}},
                {"path": "album/track2.mp3", "size": 200, "mtime": 1234567891, "permissions": "644", "is_audio": True, "audio_info": {}},
                {"path": "other/file.txt", "size": 50, "mtime": 1234567892, "permissions": "644", "is_audio": False, "audio_info": {}}
            ]
        }
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        # List root directory
        root_items = faker.listdir(".")
        assert set(root_items) == {"album", "other"}

        # List album subdirectory
        album_items = faker.listdir("album")
        assert album_items == ["track1.flac", "track2.mp3"]

    def test_stat(self, tmp_path: Path) -> None:
        """Test stat() returns correct stat results."""
        metadata = {"files": [{"path": "test.txt", "size": 12345, "mtime": 1234567890, "permissions": "755", "is_audio": False, "audio_info": {}}]}
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        stat_result = faker.stat("test.txt")

        assert stat_result.st_size == 12345
        assert stat_result.st_mtime == 1234567890.0
        assert stat_result.st_mode & 0o755 == 0o755  # Check permissions

        with pytest.raises(FileNotFoundError):
            faker.stat("nonexistent.txt")

    def test_path_normalization(self, tmp_path: Path) -> None:
        """Test that path separators are normalized."""
        metadata = {"files": [{"path": "test/file.txt", "size": 100, "mtime": 1234567890, "permissions": "644", "is_audio": False, "audio_info": {}}]}
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        # Test with backslashes (should be normalized)
        assert faker.exists("test\\file.txt") is True
        assert faker.isfile("test\\file.txt") is True

    def test_open_not_implemented(self, tmp_path: Path) -> None:
        """Test that file opening raises NotImplementedError."""
        metadata = {"files": [{"path": "test.txt", "size": 100, "mtime": 1234567890, "permissions": "644", "is_audio": False, "audio_info": {}}]}
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)

        with pytest.raises(NotImplementedError, match="File reading not supported"):
            faker.open("test.txt")


class TestFakerIntegration:
    """Test FilesystemFaker integration utilities."""

    def test_create_faker_for_corpus_custom_path(self, tmp_path: Path) -> None:
        """Test create_faker_for_corpus with custom path."""
        corpus_dir = tmp_path / "custom_corpus"
        corpus_dir.mkdir()
        metadata_file = corpus_dir / "metadata.json"
        metadata_file.write_text('{"files": []}')

        faker = create_faker_for_corpus(corpus_dir)
        assert len(faker._file_index) == 0

    def test_faker_context_interface(self, tmp_path: Path) -> None:
        """Test that FakerContext can be created and has expected interface."""
        metadata = {"files": [{"path": "test.txt", "size": 100, "mtime": 1234567890, "permissions": "644", "is_audio": False, "audio_info": {}}]}
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata))

        faker = FilesystemFaker(metadata_file)
        context = FakerContext(faker)

        # Verify context has expected interface
        assert hasattr(context, '__enter__')
        assert hasattr(context, '__exit__')
        assert context.faker is faker
