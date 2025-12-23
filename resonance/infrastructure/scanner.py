"""Directory and file scanner for audio files."""

from __future__ import annotations

import fnmatch
import json
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
    """Scans filesystem for audio files and groups them by directory.

    Symlink policy: do not follow symlinked directories and skip symlinked files.
    """

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
        batches: list[DirectoryBatch] = []
        for root in self.roots:
            if not root.exists():
                continue

            for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                dirnames.sort()
                filenames.sort()
                directory = Path(dirpath)
                files: list[Path] = []
                non_audio: list[Path] = []

                for name in filenames:
                    file_path = directory / name
                    if not file_path.is_file() or file_path.is_symlink():
                        continue
                    if self._should_include(file_path):
                        files.append(file_path)
                    else:
                        non_audio.append(file_path)

                if files:
                    signature = dir_signature(files)
                    batches.append(
                        DirectoryBatch(
                            directory=directory,
                            files=sorted(files),
                            non_audio_files=sorted(non_audio),
                            signature_hash=signature.signature_hash,
                            dir_id=dir_id(signature),
                        )
                    )
        yield from self._merge_batches(batches)

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
            if path.is_file() and not path.is_symlink() and self._should_include(path)
        ]
        non_audio = [
            path
            for path in directory.iterdir()
            if path.is_file() and not path.is_symlink() and not self._should_include(path)
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

    def _merge_batches(self, batches: list[DirectoryBatch]) -> list[DirectoryBatch]:
        if not batches:
            return []
        grouped: dict[tuple[Path, str], list[DirectoryBatch]] = {}
        ungrouped: list[DirectoryBatch] = []
        for batch in batches:
            album_key = self._album_key(batch)
            if album_key is None:
                ungrouped.append(batch)
                continue
            root = self._root_for_batch(batch)
            grouped.setdefault((root, album_key), []).append(batch)

        merged: list[DirectoryBatch] = []
        for _, group in sorted(
            grouped.items(),
            key=lambda item: (str(item[0][0]), item[0][1]),
        ):
            if len(group) == 1:
                merged.append(group[0])
                continue
            files = sorted({path for batch in group for path in batch.files})
            non_audio = sorted({path for batch in group for path in batch.non_audio_files})
            signature = dir_signature(files)
            directory = self._merge_directory(group)
            merged.append(
                DirectoryBatch(
                    directory=directory,
                    files=files,
                    non_audio_files=non_audio,
                    signature_hash=signature.signature_hash,
                    dir_id=dir_id(signature),
                )
            )
        return merged + ungrouped

    def _album_key(self, batch: DirectoryBatch) -> str | None:
        for path in batch.files:
            tags = self._read_stub_tags(path)
            album = tags.get("album")
            artist = tags.get("album_artist") or tags.get("artist")
            if album and artist:
                return f"{artist.strip().lower()}::{album.strip().lower()}"
        return None

    def _read_stub_tags(self, path: Path) -> dict[str, str]:
        metadata_path = path.with_suffix(path.suffix + ".meta.json")
        if not metadata_path.exists():
            return {}
        try:
            data = json.loads(metadata_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
        tags = data.get("tags")
        return tags if isinstance(tags, dict) else {}

    def _root_for_batch(self, batch: DirectoryBatch) -> Path:
        for root in self.roots:
            try:
                batch.directory.resolve().relative_to(root.resolve())
            except ValueError:
                continue
            return root.resolve()
        return batch.directory.resolve()

    def _merge_directory(self, group: list[DirectoryBatch]) -> Path:
        def key(batch: DirectoryBatch) -> tuple[int, str]:
            return (-len(batch.files), str(batch.directory))

        return sorted(group, key=key)[0].directory
