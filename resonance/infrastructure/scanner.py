"""Directory and file scanner for audio files."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DirectoryBatch:
    """A directory containing audio files."""
    directory: Path
    files: list[Path]


class LibraryScanner:
    """Scans filesystem for audio files and groups them by directory."""

    DEFAULT_EXTENSIONS = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav"}

    def __init__(
        self,
        roots: list[Path],
        extensions: set[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        """Initialize scanner.

        Args:
            roots: List of root directories to scan
            extensions: Set of file extensions to include (default: .mp3, .flac, .m4a, etc.)
            exclude_patterns: List of fnmatch patterns to exclude
        """
        self.roots = roots
        self.extensions = extensions or self.DEFAULT_EXTENSIONS
        self.exclude_patterns = exclude_patterns or []

    def iter_directories(self) -> Iterator[DirectoryBatch]:
        """Iterate over all directories containing audio files.

        Yields:
            DirectoryBatch objects with directory path and list of audio files
        """
        for root in self.roots:
            if not root.exists():
                continue

            for dirpath, _, filenames in os.walk(root):
                directory = Path(dirpath)
                files: list[Path] = []

                for name in filenames:
                    file_path = directory / name
                    if not file_path.is_file():
                        continue
                    if not self._should_include(file_path):
                        continue
                    files.append(file_path)

                if files:
                    yield DirectoryBatch(directory=directory, files=files)

    def collect_directory(self, directory: Path) -> DirectoryBatch | None:
        """Collect audio files from a single directory.

        Args:
            directory: Directory to scan

        Returns:
            DirectoryBatch if directory contains audio files, None otherwise
        """
        if not directory.exists() or not directory.is_dir():
            return None

        files = [
            path
            for path in directory.iterdir()
            if path.is_file() and self._should_include(path)
        ]

        if not files:
            return None

        return DirectoryBatch(directory=directory, files=files)

    def _should_include(self, path: Path) -> bool:
        """Check if file should be included based on extension and exclude patterns."""
        if path.suffix.lower() not in self.extensions:
            return False

        rel = str(path)
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(rel, pattern):
                return False

        return True
