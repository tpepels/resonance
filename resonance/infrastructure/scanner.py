"""Directory and file scanner for audio files."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from resonance.core.identity import dir_signature, dir_id


@dataclass
class DirectoryBatch:
    """A directory containing audio and non-audio files."""
    directory: Path
    files: list[Path]
    non_audio_files: list[Path]
    signature_hash: str
    dir_id: str


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
            DirectoryBatch objects with directory path and file lists
        """
        for root in self.roots:
            if not root.exists():
                continue

            for dirpath, dirnames, filenames in os.walk(root):
                dirnames.sort()
                filenames.sort()
                directory = Path(dirpath)
                files: list[Path] = []
                non_audio: list[Path] = []

                for name in filenames:
                    file_path = directory / name
                    if not file_path.is_file():
                        continue
                    if self._should_include(file_path):
                        files.append(file_path)
                    else:
                        non_audio.append(file_path)

                if files:
                    signature = dir_signature(files)
                    yield DirectoryBatch(
                        directory=directory,
                        files=sorted(files),
                        non_audio_files=sorted(non_audio),
                        signature_hash=signature.signature_hash,
                        dir_id=dir_id(signature),
                    )

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
        non_audio = [
            path
            for path in directory.iterdir()
            if path.is_file() and not self._should_include(path)
        ]

        if not files:
            return None

        signature = dir_signature(sorted(files))
        return DirectoryBatch(
            directory=directory,
            files=sorted(files),
            non_audio_files=sorted(non_audio),
            signature_hash=signature.signature_hash,
            dir_id=dir_id(signature),
        )

    def _should_include(self, path: Path) -> bool:
        """Check if file should be included based on extension and exclude patterns."""
        if path.suffix.lower() not in self.extensions:
            return False

        rel = str(path)
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(rel, pattern):
                return False

        return True
