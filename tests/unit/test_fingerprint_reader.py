"""Unit tests for FingerprintReader."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from resonance.core.fingerprint import FingerprintReader


class TestFingerprintReader:
    """Test FingerprintReader functionality."""

    def test_fingerprint_reader_initialization(self) -> None:
        """Test FingerprintReader initializes correctly."""
        reader = FingerprintReader()
        assert reader.acoustid_api_key is None
        assert reader._pyacoustid is None

        reader_with_key = FingerprintReader("test-key")
        assert reader_with_key.acoustid_api_key == "test-key"

    def test_read_fingerprint_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that non-existent files return None."""
        reader = FingerprintReader()
        nonexistent = tmp_path / "nonexistent.flac"

        result = reader.read_fingerprint(nonexistent)
        assert result is None

    def test_read_fingerprint_empty_file(self, tmp_path: Path) -> None:
        """Test that empty files return None."""
        reader = FingerprintReader()
        empty_file = tmp_path / "empty.flac"

        # Create empty file and ensure it's properly closed
        with open(empty_file, 'w') as f:
            f.write("")

        result = reader.read_fingerprint(empty_file)
        assert result is None

    def test_read_fingerprint_pyacoustid_not_available(self, tmp_path: Path) -> None:
        """Test graceful handling when pyacoustid is not available."""
        reader = FingerprintReader()
        test_file = tmp_path / "test.flac"
        test_file.write_text("fake audio")

        # Mock ImportError for both possible module names
        with patch.dict('sys.modules', {'acoustid': None, 'pyacoustid': None}):
            result = reader.read_fingerprint(test_file)
            assert result is None

    def test_read_fingerprint_success(self, tmp_path: Path) -> None:
        """Test successful fingerprint extraction."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        from unittest.mock import patch

        with patch('acoustid.fingerprint_file') as mock_fingerprint:
            mock_fingerprint.return_value = (180.5, "test_fingerprint_data")

            reader = FingerprintReader()
            test_file = tmp_path / "test.flac"
            test_file.write_text("fake audio")

            result = reader.read_fingerprint(test_file)

            assert result == "test_fingerprint_data"
            mock_fingerprint.assert_called_once_with(str(test_file))

    def test_read_fingerprint_no_backend_error(self, tmp_path: Path) -> None:
        """Test handling of NoBackendError."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        from unittest.mock import patch

        with patch('acoustid.fingerprint_file') as mock_fingerprint:
            # Create a custom exception class to simulate NoBackendError
            class MockNoBackendError(Exception):
                pass
            MockNoBackendError.__name__ = "NoBackendError"

            mock_fingerprint.side_effect = MockNoBackendError("No audio backend available")

            reader = FingerprintReader()
            test_file = tmp_path / "test.flac"
            test_file.write_text("fake audio")

            result = reader.read_fingerprint(test_file)
            assert result is None

    def test_read_fingerprint_generation_error(self, tmp_path: Path) -> None:
        """Test handling of FingerprintGenerationError."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        from unittest.mock import patch

        with patch('acoustid.fingerprint_file') as mock_fingerprint:
            # Create a custom exception class to simulate FingerprintGenerationError
            class MockFingerprintGenerationError(Exception):
                pass
            MockFingerprintGenerationError.__name__ = "FingerprintGenerationError"

            mock_fingerprint.side_effect = MockFingerprintGenerationError("Fingerprint generation failed")

            reader = FingerprintReader()
            test_file = tmp_path / "test.flac"
            test_file.write_text("fake audio")

            result = reader.read_fingerprint(test_file)
            assert result is None

    def test_read_fingerprint_invalid_format(self, tmp_path: Path) -> None:
        """Test handling of invalid fingerprint format."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        from unittest.mock import patch

        reader = FingerprintReader()
        test_file = tmp_path / "test.flac"
        test_file.write_text("fake audio")

        # Test empty fingerprint
        with patch('acoustid.fingerprint_file', return_value=(180.5, "")):
            result = reader.read_fingerprint(test_file)
            assert result is None

        # Test non-string fingerprint
        with patch('acoustid.fingerprint_file', return_value=(180.5, 12345)):
            result = reader.read_fingerprint(test_file)
            assert result is None

    def test_read_duration_success(self, tmp_path: Path) -> None:
        """Test successful duration extraction."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        from unittest.mock import patch

        with patch('acoustid.fingerprint_file', return_value=(180.7, "fingerprint")):
            reader = FingerprintReader()
            test_file = tmp_path / "test.flac"
            test_file.write_text("fake audio")

            result = reader.read_duration(test_file)

            assert result == 181  # Rounded to nearest second

    def test_read_duration_nonexistent_file(self, tmp_path: Path) -> None:
        """Test duration extraction for non-existent files."""
        reader = FingerprintReader()
        nonexistent = tmp_path / "nonexistent.flac"

        result = reader.read_duration(nonexistent)
        assert result is None

    def test_read_duration_pyacoustid_unavailable(self, tmp_path: Path) -> None:
        """Test duration extraction when pyacoustid is unavailable."""
        reader = FingerprintReader()
        test_file = tmp_path / "test.flac"
        test_file.write_text("fake audio")

        with patch.dict('sys.modules', {'acoustid': None, 'pyacoustid': None}):
            result = reader.read_duration(test_file)
            assert result is None

    def test_read_duration_rounding(self, tmp_path: Path) -> None:
        """Test that duration is properly rounded."""
        try:
            import acoustid
        except ImportError:
            pytest.skip("acoustid not available")
            return

        from unittest.mock import patch

        test_cases = [
            (180.1, 180),
            (180.5, 181),  # Rounds up
            (180.9, 181),
            (179.4, 179),  # Rounds down
        ]

        reader = FingerprintReader()
        test_file = tmp_path / "test.flac"
        test_file.write_text("fake audio")

        for input_duration, expected in test_cases:
            with patch('acoustid.fingerprint_file', return_value=(input_duration, "fingerprint")):
                result = reader.read_duration(test_file)
                assert result == expected, f"Failed for {input_duration}: expected {expected}, got {result}"
