"""Unit tests for FileService."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from resonance.services.file_service import FileService


class TestFileService:
    """Test FileService functionality."""

    def test_init(self):
        """Test FileService initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            library_root = Path(temp_dir)
            service = FileService(library_root)

            assert service.library_root == library_root
            assert service.dry_run is False

    def test_init_with_dry_run(self):
        """Test FileService initialization with dry run."""
        with tempfile.TemporaryDirectory() as temp_dir:
            library_root = Path(temp_dir)
            service = FileService(library_root, dry_run=True)

            assert service.library_root == library_root
            assert service.dry_run is True

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = FileService(Path(temp_dir))

            # Test basic sanitization (uses validation.sanitize_filename which replaces with spaces)
            assert service.sanitize_filename("Hello World") == "Hello World"
            assert service.sanitize_filename("Hello/World") == "Hello World"
            assert service.sanitize_filename("Hello\\World") == "Hello World"
            assert service.sanitize_filename("Hello:World") == "Hello World"
            assert service.sanitize_filename("Hello*World") == "Hello World"

    def test_move_track_basic(self):
        """Test basic track moving."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            service = FileService(temp_path)

            # Create source file
            source = temp_path / "source" / "track.mp3"
            source.parent.mkdir(parents=True)
            source.write_text("test content")

            # Move to destination
            dest_dir = temp_path / "dest"
            result = service.move_track(source, dest_dir)

            # Check result
            expected_dest = dest_dir / "track.mp3"
            assert result == expected_dest
            assert expected_dest.exists()
            assert not source.exists()

    def test_move_track_with_conflict_resolution(self):
        """Test track moving with conflict resolution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            service = FileService(temp_path)

            # Create source file
            source = temp_path / "source" / "track.mp3"
            source.parent.mkdir(parents=True)
            source.write_text("source content")

            # Create existing destination file
            dest_dir = temp_path / "dest"
            dest_dir.mkdir()
            existing = dest_dir / "track.mp3"
            existing.write_text("existing content")

            # Move source (should get _1 suffix)
            result = service.move_track(source, dest_dir)

            # Check result
            expected_dest = dest_dir / "track_1.mp3"
            assert result == expected_dest
            assert expected_dest.exists()
            assert existing.exists()  # Original should still be there
            assert not source.exists()

    def test_move_track_same_source_dest(self):
        """Test moving when source and destination are the same."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            service = FileService(temp_path)

            # Create source file
            source = temp_path / "track.mp3"
            source.write_text("test content")

            # Try to move to same location
            result = service.move_track(source, temp_path)

            # Should return the same path and not move anything
            assert result == source
            assert source.exists()

    def test_move_track_dry_run(self):
        """Test track moving in dry run mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            service = FileService(temp_path, dry_run=True)

            # Create source file
            source = temp_path / "source" / "track.mp3"
            source.parent.mkdir(parents=True)
            source.write_text("test content")

            # Move to destination (dry run)
            dest_dir = temp_path / "dest"
            result = service.move_track(source, dest_dir)

            # Check result - should return expected path but not actually move
            expected_dest = dest_dir / "track.mp3"
            assert result == expected_dest
            assert source.exists()  # Source should still exist
            assert not expected_dest.exists()  # Dest should not be created

    def test_delete_if_empty_already_empty(self):
        """Test deleting an already empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            service = FileService(temp_path)

            # Create empty directory
            empty_dir = temp_path / "empty"
            empty_dir.mkdir()

            # Delete it
            result = service.delete_if_empty(empty_dir)

            assert result is True
            assert not empty_dir.exists()

    def test_delete_if_empty_with_files(self):
        """Test not deleting directory that contains files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            service = FileService(temp_path)

            # Create directory with file
            dir_with_file = temp_path / "has_file"
            dir_with_file.mkdir()
            (dir_with_file / "file.txt").write_text("content")

            # Try to delete it
            result = service.delete_if_empty(dir_with_file)

            assert result is False
            assert dir_with_file.exists()

    def test_delete_if_empty_with_audio_files(self):
        """Test not deleting directory that contains audio files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            service = FileService(temp_path)

            # Create directory with audio file
            dir_with_audio = temp_path / "has_audio"
            dir_with_audio.mkdir()
            (dir_with_audio / "track.mp3").write_text("audio content")

            # Try to delete it
            result = service.delete_if_empty(dir_with_audio)

            assert result is False
            assert dir_with_audio.exists()

    def test_delete_if_empty_with_nonaudio_delete_enabled(self):
        """Test deleting directory with non-audio files when delete_nonaudio=True."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            service = FileService(temp_path)

            # Create directory with non-audio file
            dir_with_nonaudio = temp_path / "has_nonaudio"
            dir_with_nonaudio.mkdir()
            (dir_with_nonaudio / "cover.jpg").write_text("image content")

            # Delete with nonaudio deletion enabled
            result = service.delete_if_empty(dir_with_nonaudio, delete_nonaudio=True)

            assert result is True
            assert not dir_with_nonaudio.exists()

    def test_delete_if_empty_outside_library_root(self):
        """Test not deleting directories outside library root."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            service = FileService(temp_path / "library")  # Library root is subdirectory

            # Create directory outside library root
            outside_dir = temp_path / "outside"
            outside_dir.mkdir()

            # Try to delete it (should fail safety check)
            result = service.delete_if_empty(outside_dir)

            assert result is False
            assert outside_dir.exists()

    def test_delete_if_empty_nonexistent_directory(self):
        """Test handling of non-existent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            service = FileService(temp_path)

            nonexistent = temp_path / "nonexistent"

            result = service.delete_if_empty(nonexistent)

            assert result is False
