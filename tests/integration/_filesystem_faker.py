"""Filesystem faker for real-world corpus testing.

Provides filesystem operations using extracted metadata instead of real disk access.
Transparent to existing Resonance code - implements the same APIs.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, Optional


class FilesystemFaker:
    """Filesystem faker that serves from extracted metadata.

    Provides the same interface as standard Python filesystem operations
    but returns data from a pre-extracted metadata JSON file instead of
    accessing the real filesystem.

    This enables testing against real-world library structures without
    copying large music files or depending on external filesystem state.
    """

    def __init__(self, metadata_path: str | Path):
        """Initialize faker with metadata file.

        Args:
            metadata_path: Path to metadata.json file
        """
        self.metadata_path = Path(metadata_path)
        self._metadata: dict[str, Any] = {}
        self._file_index: dict[str, dict[str, Any]] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load and index metadata from JSON file."""
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {self.metadata_path}")

        with open(self.metadata_path, 'r', encoding='utf-8') as f:
            self._metadata = json.load(f)

        # Index files by path for fast lookup
        self._file_index = {}
        for file_info in self._metadata.get('files', []):
            path = file_info['path']
            self._file_index[path] = file_info

    def _get_file_info(self, path: str | Path) -> Optional[dict[str, Any]]:
        """Get file info for a given path."""
        path_str = str(path)
        # Normalize path separators
        path_str = path_str.replace('\\', '/')
        return self._file_index.get(path_str)

    def _path_exists(self, path: str | Path) -> bool:
        """Check if path exists in metadata."""
        return self._get_file_info(path) is not None

    def _is_dir(self, path: str | Path) -> bool:
        """Check if path is a directory."""
        path_str = str(path)
        # A path is considered a directory if any file starts with this path + /
        path_with_sep = path_str.rstrip('/') + '/'
        for file_path in self._file_index.keys():
            if file_path.startswith(path_with_sep):
                return True
        return False

    def _is_file(self, path: str | Path) -> bool:
        """Check if path is a file."""
        return self._get_file_info(path) is not None

    # Standard os.path interface
    def exists(self, path: str | Path) -> bool:
        """os.path.exists() compatible."""
        return self._path_exists(path) or self._is_dir(path)

    def isfile(self, path: str | Path) -> bool:
        """os.path.isfile() compatible."""
        return self._is_file(path)

    def isdir(self, path: str | Path) -> bool:
        """os.path.isdir() compatible."""
        return self._is_dir(path)

    def getsize(self, path: str | Path) -> int:
        """os.path.getsize() compatible."""
        file_info = self._get_file_info(path)
        if file_info:
            return file_info.get('size', 0)
        raise FileNotFoundError(f"No such file: {path}")

    def getmtime(self, path: str | Path) -> float:
        """os.path.getmtime() compatible."""
        file_info = self._get_file_info(path)
        if file_info:
            return float(file_info.get('mtime', 0))
        raise FileNotFoundError(f"No such file: {path}")

    # os.listdir interface
    def listdir(self, path: str | Path = '.') -> list[str]:
        """os.listdir() compatible."""
        path_str = str(path).rstrip('/')
        if path_str == '.':
            path_str = ''

        # Find all items under this path
        items = set()
        path_prefix = path_str + '/' if path_str else ''

        for file_path in self._file_index.keys():
            if file_path.startswith(path_prefix):
                # Get the next path component
                remaining = file_path[len(path_prefix):]
                if '/' in remaining:
                    # This is a subdirectory
                    item = remaining.split('/')[0]
                    items.add(item)
                else:
                    # This is a file in the current directory
                    items.add(remaining)

        return sorted(items)

    # os.stat interface
    def stat(self, path: str | Path, *, dir_fd=None, follow_symlinks=True) -> os.stat_result:
        """os.stat() compatible."""
        file_info = self._get_file_info(path)
        if not file_info:
            raise FileNotFoundError(f"No such file: {path}")

        # Create a fake stat result
        size = file_info.get('size', 0)
        mtime = file_info.get('mtime', 0)
        permissions = int(file_info.get('permissions', '644'), 8)

        # Create stat result tuple (st_mode, st_ino, st_dev, st_nlink, st_uid, st_gid, st_size, st_atime, st_mtime, st_ctime)
        stat_result = os.stat_result((
            stat.S_IFREG | permissions,  # st_mode (regular file with permissions)
            0,  # st_ino (inode - fake)
            0,  # st_dev (device - fake)
            1,  # st_nlink (number of hard links - fake)
            0,  # st_uid (user id - fake)
            0,  # st_gid (group id - fake)
            size,  # st_size
            mtime,  # st_atime (access time - use mtime)
            mtime,  # st_mtime (modification time)
            mtime,  # st_ctime (creation time - use mtime)
        ))

        return stat_result

    # pathlib.Path compatibility
    def iterdir(self, path: str | Path = '.') -> list[Path]:
        """pathlib.Path.iterdir() compatible."""
        items = self.listdir(path)
        base_path = Path(path)
        return [base_path / item for item in items]

    def glob(self, pattern: str, path: str | Path = '.') -> list[Path]:
        """Basic glob support for common patterns."""
        # Simple implementation - could be enhanced for more complex patterns
        import fnmatch
        items = self.listdir(path)
        base_path = Path(path)
        matches = []

        for item in items:
            if fnmatch.fnmatch(item, pattern):
                matches.append(base_path / item)

        return matches

    # File opening (limited support)
    def open(self, path: str | Path, mode: str = 'r', **kwargs):
        """Limited file opening support."""
        # For now, raise an error - most tests shouldn't need to read file contents
        # If needed in the future, could return a fake file-like object
        raise NotImplementedError(
            f"File reading not supported by FilesystemFaker. "
            f"Path: {path}. Use metadata-only testing."
        )


# Monkey patching utilities for testing
class FakerContext:
    """Context manager for monkey-patching filesystem operations."""

    def __init__(self, faker: FilesystemFaker):
        self.faker = faker
        self._originals = {}

    def _create_fallback_wrapper(self, faker_method, original_method):
        """Create a wrapper that tries faker first, then falls back to original."""
        def wrapper(*args, **kwargs):
            try:
                return faker_method(*args, **kwargs)
            except (FileNotFoundError, KeyError):
                # If faker doesn't have the file, fall back to real filesystem
                return original_method(*args, **kwargs)
        return wrapper

    def __enter__(self):
        # Monkey patch standard library functions with fallback behavior
        import os.path

        # Store originals
        self._originals['os.path.exists'] = os.path.exists
        self._originals['os.path.isfile'] = os.path.isfile
        self._originals['os.path.isdir'] = os.path.isdir
        self._originals['os.path.getsize'] = os.path.getsize
        self._originals['os.path.getmtime'] = os.path.getmtime
        self._originals['os.listdir'] = os.listdir
        self._originals['os.stat'] = os.stat

        # Apply patches with fallback
        os.path.exists = self._create_fallback_wrapper(self.faker.exists, os.path.exists)
        os.path.isfile = self._create_fallback_wrapper(self.faker.isfile, os.path.isfile)
        os.path.isdir = self._create_fallback_wrapper(self.faker.isdir, os.path.isdir)
        os.path.getsize = self._create_fallback_wrapper(self.faker.getsize, os.path.getsize)
        os.path.getmtime = self._create_fallback_wrapper(self.faker.getmtime, os.path.getmtime)
        os.listdir = self._create_fallback_wrapper(self.faker.listdir, os.listdir)
        os.stat = self._create_fallback_wrapper(self.faker.stat, os.stat)

        return self.faker

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore originals
        import os.path

        for name, original in self._originals.items():
            if name == 'os.path.exists':
                os.path.exists = original
            elif name == 'os.path.isfile':
                os.path.isfile = original
            elif name == 'os.path.isdir':
                os.path.isdir = original
            elif name == 'os.path.getsize':
                os.path.getsize = original
            elif name == 'os.path.getmtime':
                os.path.getmtime = original
            elif name == 'os.listdir':
                os.listdir = original
            elif name == 'os.stat':
                os.stat = original


def create_faker_for_corpus(corpus_root: str | Path | None = None) -> FilesystemFaker:
    """Create a filesystem faker for the real-world corpus.

    Args:
        corpus_root: Path to corpus directory (default: tests/real_corpus)

    Returns:
        Configured FilesystemFaker
    """
    if corpus_root is None:
        # Default to tests/real_corpus relative to this file
        corpus_root = Path(__file__).parent.parent / 'real_corpus'

    metadata_path = Path(corpus_root) / 'metadata.json'
    return FilesystemFaker(metadata_path)
